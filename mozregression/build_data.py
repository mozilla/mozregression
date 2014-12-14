from concurrent import futures
import requests
from mozlog.structured import get_default_logger
import copy
import re
import threading
import datetime

from mozregression import errors
from mozregression.utils import url_links


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
     - del data[i] # delete index

    Subclasses must implement :meth:`_create_fetch_task`.
    """
    def __init__(self, associated_data, half_window_range=4):
        self._cache = [[None, ad] for ad in associated_data]
        self.half_window_range = half_window_range
        self._logger = get_default_logger('Build Finder')

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

    def __delitem__(self, i):
        del self._cache[i]

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
                bound = min(size, self.half_window_range*2)
                range_min.extend(range(0, bound))
            if self[-1] is None:
                self._logger.debug("We need to fetch the higher limit")
                bound = max(0, size - self.half_window_range*2)
                range_max.extend(range(bound, size))

            # restrict the number of builds to fetch
            range_to_update = set(range_min + range_max)
            while len(range_to_update) > self.half_window_range*2:
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

        nb_try = 0
        while builds_to_get:
            nb_try += 1
            with futures.ThreadPoolExecutor(max_workers=8) as executor:
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
                                self._logger.warning("Got HTTPError - retrying")
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

    :param build_regex: a regexp or string regexp that can match the build file.
    :param build_info_regex: a regexp or string regexp that can match the build
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
            if not 'build_url' in data and self.build_regex.match(link):
                data['build_url'] = url + link
            elif not 'build_txt_url' in data and self.build_info_regex.match(link):
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
        response = requests.get(url)
        for line in response.text.splitlines():
            if '/rev/' in line:
                repository, changeset = line.split('/rev/')
                data['repository'] = repository
                data['changeset'] = changeset
                break
        return data

class MozBuildData(BuildData):
    """
    A BuildData like class that is able to understand the format of
    mozilla build folders with the help of :class:`BuildFolderInfoFetcher`.

    Subclasses must implement :meth:`get_build_urls`.
    """
    def __init__(self, associated_data, info_fetcher,
                 half_window_range=4, read_txt_content=False):
        BuildData.__init__(self, associated_data,
                           half_window_range=half_window_range)
        self.info_fetcher = info_fetcher
        self.read_txt_content = read_txt_content

    def get_build_urls(self, i):
        """
        Must return a list of build folder urls for the given index.

        Be careful that you are in a thread here.
        """
        raise NotImplementedError

    def is_valid_build(self, build_info):
        """
        Indicate if a build folder is valid. By default, it check for the
        existence of the build file and the build info file.

        Be careful that you are in a thread here.
        """
        return 'build_url' in build_info and 'build_txt_url' in build_info

    def _create_fetch_task(self, executor, i):
        return executor.submit(self._get_valid_build, i)

    def _get_valid_build(self, i):
        for build_url in self.get_build_urls(i):
            build_info = self.info_fetcher.find_build_info(build_url,
                                                           self.read_txt_content)
            if self.is_valid_build(build_info):
                return build_info
        return False

class InboundBuildData(MozBuildData):
    def __init__(self, associated_data, info_fetcher, raw_revisions, **kwargs):
        MozBuildData.__init__(self, associated_data, info_fetcher, **kwargs)
        self.raw_revisions = raw_revisions
        self.read_txt_content = True

    def get_build_urls(self, i):
        # there is only one candidate for the inbound build url at a given index
        return (self.get_associated_data(i)[0],)

    def _set_data(self, i, data):
        if data is not False:
            data['timestamp'] = self.get_associated_data(i)[1]
            data['revision'] = data['changeset'][:8]
        MozBuildData._set_data(self, i, data)

    def is_valid_build(self, build_info):
        valid = MozBuildData.is_valid_build(self, build_info)
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
        :meth:`NightlyBuildData.get_build_urls`.
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
    def __init__(self, good_date, bad_date, fetch_config, **kwargs):
        associated_data = range((bad_date - good_date).days + 1)
        info_fetcher = BuildFolderInfoFetcher(fetch_config.build_regex(),
                                              fetch_config.build_info_regex())
        MozBuildData.__init__(self, associated_data, info_fetcher, **kwargs)
        self.start_date = good_date
        url_builder = NightlyUrlBuilder(fetch_config)
        self.url_builder = url_builder
        self.fetch_config = fetch_config

    def get_date_for_index(self, i):
        days = self.get_associated_data(i)
        return self.start_date + datetime.timedelta(days=days)

    def get_build_urls(self, i):
        date = self.get_date_for_index(i)
        return self.url_builder.get_urls(date)

    def get_build_infos_for_date(self, date, read_txt_content=True):
        for build_url in self.url_builder.get_urls(date):
            build_info = self.info_fetcher.find_build_info(build_url,
                                                           read_txt_content)
            if self.is_valid_build(build_info):
                return build_info
        return {}
