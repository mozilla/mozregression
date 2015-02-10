from concurrent import futures
import requests
from mozlog.structured import get_default_logger
import copy
import re
import threading
import datetime

from mozregression import errors
from mozregression.utils import url_links, get_http_session


class BuildData(object):

    """
    Represents some build data available, designed to be used in
    bisection.

    It allows the lazy loading of build data, by fetching only the lower
    bound, higher bound and middle points when required.

    As some build folders are not valid - and we can know that only
    after really fetching data - there is some imprecision on data
    size which may reduce when you call ensure_limits or mid_point.

    An instance of BuildData acts like a list, ensuring following
    methods:
     - len(data) # size
     - data[1:]  # splice
     - data[0]   # get data
     - data.deleted(i) # delete index on a new returned build data

    Subclasses must implement :meth:`_create_fetch_task`.
    """

    half_window_range = 4
    max_workers = 8

    def __init__(self, associated_data):
        self.set_cache(associated_data)
        self._logger = get_default_logger('Build Finder')

    def set_cache(self, associated_data):
        self._cache = [[None, ad] for ad in associated_data]

    def _create_fetch_task(self, executor, i):
        """
        Create a task that will really download data for the given index.

        Note that the task can not return None as it is used internally
        to indicate that data has not been fetched yet.

        If the return value is False the build dir will be considered invalid,
        and will be discarded.

        Any other value will be acessible via self[index] and the build will
        be considered valid.
        """
        raise NotImplementedError

    def __len__(self):
        return len(self._cache)

    def __getslice__(self, smin, smax):
        new_data = copy.copy(self)
        new_data._cache = self._cache[smin:smax]
        return new_data

    def __getitem__(self, i):
        return self._cache[i][0]

    def deleted(self, pos, count=1):
        new_data = copy.copy(self)
        new_data._cache = self._cache[:pos] + self._cache[pos+count:]
        return new_data

    def get_associated_data(self, i):
        return self._cache[i][1]

    def _set_data(self, i, data):
        # Update cache when data is downloaded.
        # Do not touch the cache size here.
        self._cache[i][0] = data

    def _filter_invalid_builds(self):
        self._cache = [c for c in self._cache if c[0] is not False]

    def ensure_limits(self):
        """
        Ensure we know the min and max data, fetching it if necessary.
        """
        done = False
        while not done:
            size = len(self)
            if size == 0:
                # no limits to ensure
                return

            # first we detect if we need to fetch data, and which build id's
            range_min = []
            range_max = []

            # we first get an artifically large range (double) to optimize
            # the number of build data which will be fetched.
            #
            # this way, if we have a self.half_window_range of 4 (the default)
            # and for example we don't need the lowest bound, the number of
            # data to fetch for higher bound will be 8 (full range) instead
            # of 4.
            if self[0] is None:
                self._logger.debug("We need to fetch the lower limit")
                bound = min(size, self.half_window_range * 2)
                range_min.extend(range(0, bound))
            if self[-1] is None:
                self._logger.debug("We need to fetch the higher limit")
                bound = max(0, size - self.half_window_range * 2)
                range_max.extend(range(bound, size))

            # restrict the number of builds to fetch
            range_to_update = set(range_min + range_max)
            while len(range_to_update) > self.half_window_range * 2:
                if len(range_min) > len(range_max):
                    range_min = range_min[:-1]
                else:
                    range_max = range_max[1:]
                range_to_update = set(range_min + range_max)

            if range_to_update:
                self._fetch(range_to_update)
                # we asked for some data, but it may be not suficient -
                # data may be invalid - let's check it by looping
            else:
                # data is fetched on min and max bounds, we can exit
                done = True

    def mid_point(self):
        """
        Return the middle index of the data. If 0, there is no middle
        point anymore.
        """
        while True:
            self.ensure_limits()

            size = len(self)
            if size < 3:
                # let's say that the middle point is 0 if there not at least
                # 2 points.
                return 0

            mid = size / 2

            if self[mid] is None:
                self._logger.debug('We need to fetch the mid point %d'
                                   % mid)
                # we need to fetch the middle of the data
                rmax = min(size, mid + self.half_window_range)
                rmin = max(0, mid - self.half_window_range)
                self._fetch(range(rmin, rmax))
                # maybe all fetched data was invalid and we need to
                # check it by looping
            else:
                return mid

    def _fetch(self, ids, max_try=3):
        """
        Internal method to fetch some data.
        """
        # filter the already downloaded data
        builds_to_get = [i for i in ids if self[i] is None]
        size = len(self)
        self._logger.debug("We got %d folders, we need to fetch %s"
                           % (size, sorted(builds_to_get)))

        max_workers = self.max_workers
        nb_try = 0
        while builds_to_get:
            nb_try += 1
            with futures.ThreadPoolExecutor(max_workers=max_workers) \
                    as executor:
                futures_results = {}
                for i in builds_to_get:
                    future = self._create_fetch_task(executor, i)
                    futures_results[future] = i
                for future in futures.as_completed(futures_results):
                    i = futures_results[future]
                    exc = future.exception()
                    if exc is not None:
                        must_raise = True
                        if isinstance(exc, requests.HTTPError):
                            if nb_try < max_try:
                                self._logger.warning(
                                    "Got HTTPError - retrying")
                                self._logger.warning(exc)
                                must_raise = False
                        if must_raise:
                            raise errors.DownloadError(
                                "Retrieving valid builds from %r generated an"
                                " exception: %s" % (self._cache[i][1],
                                                    exc))
                    else:
                        builds_to_get.remove(i)
                        self._set_data(i, future.result())
        self._filter_invalid_builds()
        self._logger.debug("Now we got %d folders - %d were bad"
                           % (len(self), size - len(self)))


class BuildFolderInfoFetcher(object):
    """
    Allow to retrieve information from build folders.

    :param build_regex: a regexp or string regexp that
        match the build file.

    :param build_info_regex: a regexp or string regexp
        that can match the build
                             info file (.txt).
    """
    def __init__(self, build_regex, build_info_regex):
        if isinstance(build_regex, basestring):
            build_regex = re.compile(build_regex)
        if isinstance(build_info_regex, basestring):
            build_info_regex = re.compile(build_info_regex)
        self.build_regex = build_regex
        self.build_info_regex = build_info_regex

    def find_build_info(self, url, read_txt_content=False):
        """
        Retrieve information from a build folder url.

        Returns a dict with keys build_url and build_txt_url if respectively
        a build file and a build info file are found for the url.

        If read_txt_content is True, the dict is updated with data found
        by calling :meth:`find_build_info_txt`
        """
        data = {}
        if not url.endswith('/'):
            url += '/'
        for link in url_links(url):
            if 'build_url' not in data and self.build_regex.match(link):
                data['build_url'] = url + link
            elif 'build_txt_url' not in data  \
                    and self.build_info_regex.match(link):
                data['build_txt_url'] = url + link

        if read_txt_content and 'build_txt_url' in data:
            data.update(self.find_build_info_txt(data['build_txt_url']))

        return data

    def find_build_info_txt(self, url):
        """
        Retrieve information from a build information txt file.

        Returns a dict with keys repository and changeset if information
        is found.
        """
        data = {}
        response = get_http_session().get(url)
        for line in response.text.splitlines():
            if '/rev/' in line:
                repository, changeset = line.split('/rev/')
                data['repository'] = repository
                data['changeset'] = changeset
                break
        if not data:
            # the txt file could be in an old format:
            # DATE CHANGESET
            # we can try to extract that to get the changeset at least.
            matched = re.match('^\d+ (\w+)$', response.text.strip())
            if matched:
                data['changeset'] = matched.group(1)
        return data


class MozBuildData(BuildData):
    """
    A BuildData like class that is able to understand the format of
    mozilla build folders with the help of :class:`BuildFolderInfoFetcher`.

    Subclasses must implement :meth:`_get_valid_build`.
    """
    def __init__(self, associated_data, info_fetcher):
        BuildData.__init__(self, associated_data)
        self.info_fetcher = info_fetcher

    def _is_valid_build(self, build_info):
        """
        Indicate if a build folder is valid. By default, it check for the
        existence of the build file and the build info file.

        This must be used in :meth:`_get_valid_build` to ensure that a build
        is valid.
        """
        return 'build_url' in build_info and 'build_txt_url' in build_info

    def _create_fetch_task(self, executor, i):
        return executor.submit(self._get_valid_build, i)

    def _get_valid_build(self, i):
        """
        Must return build information (a dict) for the given index or False
        if no valid build is found.

        Be careful that you are in a thread here.
        """
        raise NotImplementedError


class PushLogsFinder(object):
    """
    Find pushlog json objects within two revisions on inbound.
    """
    def __init__(self, start_rev, end_rev, path='integration',
                 inbound_branch='mozilla-inbound'):
        self.start_rev = start_rev
        self.end_rev = end_rev
        self.path = path
        self.inbound_branch = inbound_branch

    def get_repo_url(self):
        return "https://hg.mozilla.org/%s/%s" % (self.path,
                                                 self.inbound_branch)

    def pushlog_url(self):
        return ('%s/json-pushes?fromchange=%s&tochange=%s'
                % (self.get_repo_url(), self.start_rev, self.end_rev))

    def get_pushlogs(self):
        """
        Returns pushlog json objects (python dicts) sorted by date.
        """
        # the first changeset is not taken into account in the result.
        # let's add it directly with this request
        chset_url = '%s/json-pushes?changeset=%s' % (
            self.get_repo_url(),
            self.start_rev)
        response = get_http_session().get(chset_url)
        response.raise_for_status()
        chsets = response.json()

        # now fetch all remaining changesets
        response = get_http_session().get(self.pushlog_url())
        response.raise_for_status()
        chsets.update(response.json())
        # sort pushlogs by date
        return sorted(chsets.itervalues(),
                      key=lambda push: push['date'])


class InboundBuildData(MozBuildData):
    """
    Fetch build information for all builds between start_rev and end_rev.
    """
    def __init__(self, fetch_config, start_rev, end_rev, range=60 * 60 * 4):
        MozBuildData.__init__(self, [], None)
        self.fetch_config = fetch_config
        self.raw_revisions = []
        pushlogs_finder = \
            PushLogsFinder(start_rev, end_rev,
                           inbound_branch=fetch_config.inbound_branch)

        pushlogs = pushlogs_finder.get_pushlogs()
        self._logger.debug('Found %d pushlog entries using `%s`'
                           % (len(pushlogs), pushlogs_finder.pushlog_url()))

        if len(pushlogs) < 2:
            # if we have 0 or 1 pushlog entry, we can not bisect.
            return

        start_time = pushlogs[0]['date'] - range
        end_time = pushlogs[-1]['date'] + range
        inbound_base_urls = self.fetch_config.inbound_base_urls()
        self._logger.debug(('We will look in `%s` to find build folders'
                            ' between %s and %s')
                           % (', '.join(inbound_base_urls),
                              start_time, end_time))

        build_urls = sorted(self._extract_paths(), key=lambda b: b[1])

        build_urls_in_range = [b for b in build_urls
                               if b[1] > start_time and b[1] < end_time]

        self._logger.debug(('Found %d build folders (from %s to %s), %d in'
                            ' the range')
                           % (len(build_urls),
                              build_urls[0][1],
                              build_urls[-1][1],
                              len(build_urls_in_range)))

        self.set_cache(build_urls_in_range)

        self.info_fetcher = \
            BuildFolderInfoFetcher(fetch_config.build_regex(),
                                   fetch_config.build_info_regex())

        self.raw_revisions = [push['changesets'][-1] for push in pushlogs]

    def _extract_paths(self):
        base_urls = self.fetch_config.inbound_base_urls()
        all_paths = []
        with futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures_results = {}
            for base_url in base_urls:
                future = executor.submit(url_links, base_url, regex=r'^\d+/$')
                futures_results[future] = base_url
            for future in futures.as_completed(futures_results):
                paths = future.result()
                base_url = futures_results[future]
                for path in paths:
                    timestamp = path.rstrip('/')
                    all_paths.append(("%s%s/" % (base_url, timestamp),
                                      int(timestamp)))
        return all_paths

    def _get_valid_build(self, i):
        build_url = self.get_associated_data(i)[0]
        build_info = self.info_fetcher.find_build_info(build_url, True)
        if self._is_valid_build(build_info):
            return build_info
        return False

    def _set_data(self, i, data):
        if data is not False:
            data['timestamp'] = self.get_associated_data(i)[1]
            data['revision'] = data['changeset'][:8]
        MozBuildData._set_data(self, i, data)

    def _is_valid_build(self, build_info):
        valid = MozBuildData._is_valid_build(self, build_info)
        if valid:
            # check that revision is in range
            remote_revision = build_info['changeset']
            for revision in self.raw_revisions:
                if remote_revision in revision:
                    return True
        return False


class NightlyUrlBuilder(object):
    """
    Build a url for a nightly build folder for a given instance of
    :class:`mozregression.fetch_configs.NightlyConfigMixin`.
    """
    def __init__(self, fetch_config):
        self.fetch_config = fetch_config
        self._cache_months = {}
        self._lock = threading.Lock()

    def _get_month_links(self, url):
        with self._lock:
            if url not in self._cache_months:
                self._cache_months[url] = url_links(url)
            return self._cache_months[url]

    def get_urls(self, date):
        """
        Get the url list of the build folder for a given date.

        This methods needs to be thread-safe as it is used in
        :meth:`NightlyBuildData.get_build_url`.
        """
        url = self.fetch_config.get_nighly_base_url(date)
        link_regex = re.compile(self.fetch_config.get_nightly_repo_regex(date))

        month_links = self._get_month_links(url)

        # first parse monthly list to get correct directory
        matches = []
        for dirlink in month_links:
            if link_regex.match(dirlink):
                matches.append(url + dirlink)
        # the most recent build urls first
        matches.reverse()
        return matches


class NightlyBuildData(MozBuildData):
    half_window_range = 1
    # max_workers here is not the real number of threads - see
    # see :meth:`_get_valid_build_for_date`
    max_workers = 3

    def __init__(self, fetch_config, good_date, bad_date):
        associated_data = [good_date + datetime.timedelta(days=i)
                           for i in range((bad_date - good_date).days + 1)]
        info_fetcher = BuildFolderInfoFetcher(fetch_config.build_regex(),
                                              fetch_config.build_info_regex())
        MozBuildData.__init__(self, associated_data, info_fetcher)
        url_builder = NightlyUrlBuilder(fetch_config)
        self.url_builder = url_builder
        self.fetch_config = fetch_config

    def _is_valid_build(self, build_info):
        # old nightly have no build txt info file, or the format is different
        # and incomplete - just check for the package file.
        return 'build_url' in build_info

    def _get_valid_build(self, i):
        return self._get_valid_build_for_date(self.get_associated_data(i))

    def _get_valid_build_for_date(self, date):
        # getting a valid build for a given date on nightly is tricky.
        # there is multiple possible builds folders for one date,
        # and some of them may be invalid (without binary for example)

        # to save time, we will try multiple build folders at the same
        # time in some threads. The first good one found is returned.
        build_urls = self.url_builder.get_urls(date)

        # by default we will check 2 build urls at once. That will lead us
        # to a maximum of 3 * 2 = 6 threads.
        max_workers = 2
        while build_urls:
            some = build_urls[:max_workers]
            with futures.ThreadPoolExecutor(max_workers=max_workers) \
                    as executor:
                futures_results = {}
                valid_builds = []
                for i, url in enumerate(some):
                    future = executor.submit(
                        self.info_fetcher.find_build_info, url)
                    futures_results[future] = i
                for future in futures.as_completed(futures_results):
                    i = futures_results[future]
                    infos = future.result()
                    if infos and self._is_valid_build(infos):
                        valid_builds.append((i, infos))
                if valid_builds:
                    valid_builds = sorted(valid_builds, key=lambda b: b[0])
                    build_infos = valid_builds[0][1]
                    if 'build_txt_url' in build_infos:
                        txt_url = build_infos['build_txt_url']
                        txt_infos = self.info_fetcher.find_build_info_txt(
                            txt_url)
                        build_infos.update(txt_infos)
                    return build_infos
            build_urls = build_urls[max_workers:]
        return False

    def mid_point(self):
        size = len(self)
        if size == 0:
            return 0
        # nightly builds are not often broken. There are good chances
        # that trying to fetch mid point and limits at the same time
        # will gives us enough information. This will save time in most cases.
        self._fetch(set([0, size / 2, size - 1]))
        return MozBuildData.mid_point(self)

    def get_build_infos_for_date(self, date):
        return self._get_valid_build_for_date(date) or {}
