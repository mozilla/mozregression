from concurrent import futures
import requests
from mozlog.structured import get_default_logger
import copy

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
            mid = size / 2
            if mid == 0:
                return 0

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


class InboundBuildData(BuildData):
    def __init__(self, associated_data, raw_revisions, half_window_range=4):
        BuildData.__init__(self, associated_data,
                           half_window_range=half_window_range)
        self.raw_revisions = raw_revisions

    def _create_fetch_task(self, executor, i):
        build_url, timestamp = self.get_associated_data(i)
        return executor.submit(self._get_valid_build,
                               build_url,
                               timestamp,
                               self.raw_revisions)

    def _get_valid_build(self, build_url, timestamp, raw_revisions):
        for link in url_links(build_url, regex=r'^.+\.txt$'):
            url = "%s/%s" % (build_url, link)
            response = requests.get(url)
            remote_revision = None
            for line in response.iter_lines():
                # Filter out Keep-Alive new lines.
                if not line:
                    continue
                parts = line.split('/rev/')
                if len(parts) == 2:
                    remote_revision = parts[1]
                    break  # for line
            if remote_revision:
                for revision in raw_revisions:
                    if remote_revision in revision:
                        return {
                            'revision': revision[:8],
                            'timestamp': timestamp,
                        }
        return False
