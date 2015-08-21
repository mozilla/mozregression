from concurrent import futures
import requests
from mozlog.structured import get_default_logger
import copy
import datetime

from mozregression import errors
from mozregression.network import retry_get
from mozregression.fetch_build_info import NightlyInfoFetcher, \
    InboundInfoFetcher


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

    def filter_invalid_builds(self):
        """
        Remove builds in the cache that are marked as invalid.
        """
        self._cache = [c for c in self._cache if c[0] is not False]

    def index_of(self, key):
        """
        Return the index of a cache entry that match a criteria given by key.

        Note that a cache entry is composed of [build_data, associated_data].

        :param key: a function that takes a cache entry and must returns
                    True when interesting cache entry is found.
        """
        for i, c in enumerate(self._cache):
            if key(c):
                return i
        return -1

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
        self.filter_invalid_builds()
        self._logger.debug("Now we got %d folders - %d were bad"
                           % (len(self), size - len(self)))


class MozBuildData(BuildData):
    """
    A BuildData like class that is able to understand the format of
    mozilla build folder.

    Subclasses must implement :meth:`_get_valid_build`.
    """
    def __init__(self, associated_data):
        BuildData.__init__(self, associated_data)

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

        This will return at least one pushlog. If changesets are not valid
        it will raise a MozRegressionError.
        """

        def _check_response(response):
            if response.status_code == 404:
                raise errors.MozRegressionError(
                    "The url %r returned a 404 error. Please check the"
                    " validity of the given changesets (%r, %r)." %
                    (str(response.url), self.start_rev, self.end_rev)
                )
            response.raise_for_status()

        # the first changeset is not taken into account in the result.
        # let's add it directly with this request
        chset_url = '%s/json-pushes?changeset=%s' % (
            self.get_repo_url(),
            self.start_rev)
        response = retry_get(chset_url)
        _check_response(response)
        chsets = response.json()

        # now fetch all remaining changesets
        response = retry_get(self.pushlog_url())
        _check_response(response)
        chsets.update(response.json())
        # sort pushlogs by date
        return sorted(chsets.itervalues(),
                      key=lambda push: push['date'])


class InboundBuildData(MozBuildData):
    """
    Fetch build information for all builds between start_rev and end_rev.
    """
    half_window_range = 2
    max_workers = 4

    def __init__(self, fetch_config, start_rev, end_rev):
        MozBuildData.__init__(self, [])
        self.fetch_config = fetch_config
        self.info_fetcher = InboundInfoFetcher(fetch_config)

        pushlogs_finder = \
            PushLogsFinder(start_rev, end_rev,
                           inbound_branch=fetch_config.inbound_branch)

        pushlogs = pushlogs_finder.get_pushlogs()
        self._logger.info('Found %d pushlog entries using `%s`'
                          % (len(pushlogs), pushlogs_finder.pushlog_url()))

        cache = []
        for pushlog in pushlogs:
            changeset = pushlog['changesets'][-1]
            cache.append((changeset, pushlog['date']))
        self.set_cache(cache)

    def _get_valid_build(self, i):
        changeset = self.get_associated_data(i)[0]
        try:
            return self.info_fetcher.find_build_info(changeset)
        except errors.BuildInfoNotFound:
            return False


class NightlyBuildData(MozBuildData):
    half_window_range = 1
    # max_workers here is not the real number of threads - see
    # see :meth:`_get_valid_build_for_date`
    max_workers = 3

    def __init__(self, fetch_config, good_date, bad_date):
        associated_data = [good_date + datetime.timedelta(days=i)
                           for i in range((bad_date - good_date).days + 1)]
        MozBuildData.__init__(self, associated_data)
        self.info_fetcher = NightlyInfoFetcher(fetch_config)
        self.fetch_config = fetch_config

    def _get_valid_build(self, i):
        return self._get_valid_build_for_date(self.get_associated_data(i))

    def _get_valid_build_for_date(self, date):
        try:
            return self.info_fetcher.find_build_info(date)
        except errors.BuildInfoNotFound:
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
