#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
This module provide a BuildRange class, which acts like a list of BuildInfo
objects that are loaded on demand. A BuildRange is used for bisecting builds.
"""

import copy
import datetime

from threading import Thread
from mozregression.errors import BuildInfoNotFound
from mozregression.json_pushes import JsonPushes
from mozregression.fetch_build_info import (InboundInfoFetcher,
                                            NightlyInfoFetcher)


class FutureBuildInfo(object):
    def __init__(self, build_info_fetcher, data):
        self.build_info_fetcher = build_info_fetcher
        self.data = data
        self._build_info = None

    def _fetch(self):
        return self.build_info_fetcher.find_build_info(self.data)

    @property
    def build_info(self):
        if self._build_info is None:
            try:
                self._build_info = self._fetch()
            except BuildInfoNotFound:
                self._build_info = False
        return self._build_info

    def is_available(self):
        return self._build_info is not None

    def is_valid(self):
        return self._build_info is not False


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

    def __len__(self):
        return len(self._future_build_infos)

    def __getslice__(self, smin, smax):
        new_range = copy.copy(self)
        new_range._future_build_infos = self._future_build_infos[smin:smax]
        return new_range

    def __getitem__(self, i):
        return self._future_build_infos[i].build_info

    def deleted(self, pos, count=1):
        new_range = copy.copy(self)
        new_range._future_build_infos = \
            self._future_build_infos[:pos] + \
            self._future_build_infos[pos+count:]
        return new_range

    def filter_invalid_builds(self):
        """
        Remove items that were unable to load BuildInfos.
        """
        self._future_build_infos = \
            [b for b in self._future_build_infos if b.is_valid()]

    def _fetch(self, indexes):
        indexes = set(indexes)
        need_fetch = any(not self._future_build_infos[i].is_available()
                         for i in indexes)
        if not need_fetch:
            return
        threads = [Thread(target=self.__getitem__, args=(i,))
                   for i in indexes]
        for thread in threads:
            thread.daemon = True
            thread.start()
        for thread in threads:
            while thread.is_alive():
                thread.join(0.1)

    def mid_point(self):
        """
        Return the mid point of the range.

        To find the mid point, the higher and lower limits of the range are
        accessed. Note that this method may resize the build range if some
        builds are invalids (we were not able to load build_info for some
        index)
        """
        while True:
            size = len(self)
            if size < 3:
                # let's say that the middle point is 0 if there is not at least
                # 2 points - still, fetch data if needed.
                self._fetch(range(size))
                self.filter_invalid_builds()
                return 0
            mid = size/2
            self._fetch((0, mid, size-1))
            # remove invalids
            self.filter_invalid_builds()
            if len(self) == size:
                # nothing removed, so we found valid builds only
                return mid

    def index(self, build_info):
        """
        Returns the index in the range for a given build_info.

        Note that this will only search in already loaded build_infos.
        """
        for i, fb in enumerate(self._future_build_infos):
            if fb.is_available() and build_info == fb.build_info:
                return i
        raise ValueError("%s not in build range." % build_info)


def range_for_inbounds(fetch_config, start_rev, end_rev):
    """
    Creates a BuildRange for inbounds builds.
    """
    info_fetcher = InboundInfoFetcher(fetch_config)

    pushlogs_finder = JsonPushes(branch=fetch_config.inbound_branch)
    pushlogs = pushlogs_finder.pushlog_within_changes(start_rev, end_rev)

    futures_builds = []
    for pushlog in pushlogs:
        changeset = pushlog['changesets'][-1]
        futures_builds.append(FutureBuildInfo(info_fetcher, changeset))
    return BuildRange(info_fetcher, futures_builds)


def range_for_nightlies(fetch_config, start_date, end_date):
    """
    Creates a BuildRange for inbounds nightlies.
    """
    info_fetcher = NightlyInfoFetcher(fetch_config)
    futures_builds = []
    for i in range((end_date - start_date).days + 1):
        futures_builds.append(
            FutureBuildInfo(
                info_fetcher,
                start_date + datetime.timedelta(days=i)
            )
        )
    return BuildRange(info_fetcher, futures_builds)
