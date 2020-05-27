"""
This module provide a BuildRange class, which acts like a list of BuildInfo
objects that are loaded on demand. A BuildRange is used for bisecting builds.
"""

from __future__ import absolute_import

import copy
import datetime
from threading import Thread

from mozlog import get_proxy_logger

from mozregression.dates import is_date_or_datetime, to_date, to_datetime
from mozregression.errors import BuildInfoNotFound
from mozregression.fetch_build_info import IntegrationInfoFetcher, NightlyInfoFetcher

LOG = get_proxy_logger("Bisector")


class FutureBuildInfo(object):
    def __init__(self, build_info_fetcher, data):
        self.build_info_fetcher = build_info_fetcher
        self.data = data
        self._build_info = None

    def date_or_changeset(self):
        return self.data

    def _fetch(self):
        return self.build_info_fetcher.find_build_info(self.data)

    @property
    def build_info(self):
        if self._build_info is None:
            try:
                self._build_info = self._fetch()
            except BuildInfoNotFound as exc:
                LOG.warning("Skipping build %s: %s" % (self.data, exc))
                self._build_info = False
        return self._build_info

    def is_available(self):
        return self._build_info is not None

    def is_valid(self):
        return self._build_info is not False

    def __str__(self):
        return "%s" % self.data


class TCFutureBuildInfo(FutureBuildInfo):
    def date_or_changeset(self):
        return self.data.changeset


class BuildRange(object):
    """
    Range of build infos used in bisection.

    This is initialized with instances of FutureBuildInfo that will
    load real BuildInfo instances on demand (calling :meth:`mid_point`
    or accessing data via __getitem__.

    This act like a list, providing the following methods:

     - len(build_range)  # size of the build range
     - build_range[0]  # item access, will load the build_info if needed
     - build_range[0:5]  # slice operation, return a new build_range object
     - build_range.deleted(5)  # return a new build_range without item 5
    """

    def __init__(self, build_info_fetcher, future_build_infos):
        self.build_info_fetcher = build_info_fetcher
        self._future_build_infos = future_build_infos

    @property
    def future_build_infos(self):
        return self._future_build_infos

    def __len__(self):
        return len(self._future_build_infos)

    def __getitem__(self, item):
        if isinstance(item, slice):
            if item.step not in (1, None):
                raise ValueError("only step=1 supported")
            new_range = copy.copy(self)
            new_range._future_build_infos = self._future_build_infos[item.start : item.stop]
            return new_range

        return self._future_build_infos[item].build_info

    def deleted(self, pos, count=1):
        new_range = copy.copy(self)
        new_range._future_build_infos = (
            self._future_build_infos[:pos] + self._future_build_infos[pos + count :]
        )
        return new_range

    def filter_invalid_builds(self):
        """
        Remove items that were unable to load BuildInfos.
        """
        self._future_build_infos = [b for b in self._future_build_infos if b.is_valid()]

    def _fetch(self, indexes):
        indexes = set(indexes)
        need_fetch = any(not self._future_build_infos[i].is_available() for i in indexes)
        if not need_fetch:
            return
        threads = [Thread(target=self.__getitem__, args=(i,)) for i in indexes]
        for thread in threads:
            thread.daemon = True
            thread.start()
        for thread in threads:
            while thread.is_alive():
                thread.join(0.1)

    def mid_point(self, interrupt=None):
        """
        Return the mid point of the range.

        To find the mid point, the higher and lower limits of the range are
        accessed. Note that this method may resize the build range if some
        builds are invalids (we were not able to load build_info for some
        index)

        if `interrupt` is given, it should be a callable that takes no
        arguments and returns True when you want to stop looking for the
        mid_point. In this case, StopIteration will be raised. This is provided
        because this methods may take a long time to finish, and callers may
        want to end it at some point.
        """
        while True:
            if interrupt and interrupt():
                raise StopIteration
            size = len(self)
            if size < 3:
                # let's say that the middle point is 0 if there is not at least
                # 2 points - still, fetch data if needed.
                self._fetch(list(range(size)))
                self.filter_invalid_builds()
                return 0
            mid = int(size / 2)
            self._fetch((0, mid, size - 1))
            # remove invalids
            self.filter_invalid_builds()
            if len(self) == size:
                # nothing removed, so we found valid builds only
                return int(mid)

    def check_expand(self, expand, range_before, range_after, interrupt=None):
        """
        Check the limits of the build range, expanding it if needed.

        :param expand: number of builds to try in case expanding is required
        :param range_before: a callable that takes 2 parameters,
                             (FutureBuildInfo, size) that should construct a
                             new BuildRange of the given size before the given
                             build info.
        :param range_after: same as `range_before`, but should build the range
                            after the given build info.
        :param interrupt: a callable that can interrupt the process (raising
                          StopIteration) or None.
        """
        if len(self) < 2:
            # we need at least two build to expand the range
            return

        first, last = self.get_future(0), self.get_future(-1)
        self._fetch((0, -1))
        self.filter_invalid_builds()

        if len(self) < 2:
            # we need at least two valid builds to expand the range
            return

        def _search(br, index, rng):
            while len(br):
                if interrupt and interrupt():
                    raise StopIteration
                build = br._future_build_infos[index]
                if build.is_available() and build.is_valid():
                    return build
                br._fetch(rng(len(br)))
                br.filter_invalid_builds()

        def search_first(br):
            # search the first available build in br, 3 at a time
            return _search(br, 0, lambda s: list(range(0, min(3, s))))

        def search_last(br):
            # search the last available build in br, 3 at a time
            return _search(br, -1, lambda s: list(range(max(s - 3, 0), s)))

        if self.get_future(0) != first:
            new_first = search_last(range_before(first, expand))
            if new_first:
                LOG.info("Expanding lower limit of the range to %s" % new_first)
                self._future_build_infos.insert(0, new_first)
            else:
                LOG.critical(
                    "First build %s is missing, but mozregression"
                    " can't find a build before - so it is excluded,"
                    " but it could contain the regression!" % first
                )
        if self.get_future(-1) != last:
            new_last = search_first(range_after(last, expand))
            if new_last:
                LOG.info("Expanding higher limit of the range to %s" % new_last)
                self._future_build_infos.append(new_last)
            else:
                LOG.critical(
                    "Last build %s is missing, but mozregression"
                    " can't find a build after - so it is excluded,"
                    " but it could contain the regression!" % last
                )

    def index(self, build_info):
        """
        Returns the index in the range for a given build_info.

        Note that this will only search in already loaded build_infos.
        """
        for i, fb in enumerate(self._future_build_infos):
            if fb.is_available() and build_info == fb.build_info:
                return i
        raise ValueError("%s not in build range." % build_info)

    def get_future(self, index):
        """
        Returns the FutureBuildInfo at the given index.

        Note that the FutureBuildInfo may or may not have downloaded
        the real BuildInfo yet, but it is ensured that its member `data` is
        valid.
        """
        return self._future_build_infos[index]


def _tc_build_range(future_tc, start_id, end_id):
    jpushes = future_tc.build_info_fetcher.jpushes
    futures_builds = [
        future_tc.__class__(future_tc.build_info_fetcher, push)
        for push in jpushes.pushes(startID=start_id, endID=end_id)
    ]
    return BuildRange(future_tc.build_info_fetcher, futures_builds)


def tc_range_after(future_tc, size):
    """Create a build range after a TCFutureBuildInfo"""
    return _tc_build_range(future_tc, future_tc.data.push_id, int(future_tc.data.push_id) + size)


def tc_range_before(future_tc, size):
    """Create a build range before a TCFutureBuildInfo"""
    p_id = int(future_tc.data.push_id) - 1
    return _tc_build_range(future_tc, p_id - size, p_id)


def get_integration_range(
    fetch_config, start_rev, end_rev, time_limit=None, expand=0, interrupt=None
):
    """
    Creates a BuildRange for integration builds.
    """
    info_fetcher = IntegrationInfoFetcher(fetch_config)
    jpushes = info_fetcher.jpushes

    time_limit = time_limit or (datetime.datetime.now() + datetime.timedelta(days=-365))

    def _check_date(obj):
        if is_date_or_datetime(obj):
            if to_datetime(obj) < time_limit:
                LOG.info(
                    "TaskCluster only keeps builds for one year."
                    " Using %s instead of %s." % (time_limit, obj)
                )
                obj = time_limit
        return obj

    start_rev = _check_date(start_rev)
    end_rev = _check_date(end_rev)

    futures_builds = [
        TCFutureBuildInfo(info_fetcher, push)
        for push in jpushes.pushes_within_changes(start_rev, end_rev)
    ]
    br = BuildRange(info_fetcher, futures_builds)
    if expand > 0:
        br.check_expand(expand, tc_range_before, tc_range_after, interrupt=interrupt)
    return br


def get_nightly_range(fetch_config, start_date, end_date, expand=0, interrupt=None):
    """
    Creates a BuildRange for nightlies.
    """
    info_fetcher = NightlyInfoFetcher(fetch_config)
    futures_builds = []
    # build the build range using only dates
    sd = to_date(start_date)
    for i in range((to_date(end_date) - sd).days + 1):
        futures_builds.append(FutureBuildInfo(info_fetcher, sd + datetime.timedelta(days=i)))
    # and now put back the real start and end dates
    # in case they were datetime instances (coming from buildid)
    futures_builds[0].data = start_date
    futures_builds[-1].data = end_date
    return BuildRange(info_fetcher, futures_builds)
