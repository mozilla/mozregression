#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import math
import datetime
from mozlog.structured import get_default_logger

from mozregression.build_data import NightlyBuildData, InboundBuildData
from mozregression.errors import MozRegressionError, LauncherError


def compute_steps_left(steps):
    if steps <= 1:
        return 0
    return math.trunc(math.log(steps, 2))


class BisectorHandler(object):
    """
    React to events of a :class:`Bisector`. This is intended to be subclassed.

    A BisectorHandler keep the state of the current bisection process.
    """

    def __init__(self, find_fix=False):
        self.find_fix = find_fix
        self.found_repo = None
        self.build_data = None
        self.good_revision = None
        self.bad_revision = None
        self._logger = get_default_logger('Bisector')

    def set_build_data(self, build_data):
        """
        Save a reference of the :class:`mozregression.build_data.BuildData`
        instance.

        This is called by the bisector before each step of the bisection
        process.
        """
        self.build_data = build_data

    def _print_progress(self, new_data):
        """
        Log the current state of the bisection process.
        """
        raise NotImplementedError

    def _reverse_if_find_fix(self, var1, var2):
        return (var1, var2) if not self.find_fix else (var2, var1)

    def initialize(self):
        """
        Initialize some data at the beginning of each step of a bisection
        process.

        This will only be called if there is some build data.
        """
        # these values could be missing for old inbound builds
        # until we tried the builds
        repo = self.build_data[-1].repo_url
        if repo is not None:
            # do not update repo if we can' find it now
            # else we may override a previously defined one
            self.found_repo = repo
        self.good_revision, self.bad_revision = \
            self._reverse_if_find_fix(self.build_data[0].changeset,
                                      self.build_data[-1].changeset)

    def get_pushlog_url(self):
        first_rev, last_rev = self.get_range()
        if first_rev == last_rev:
            return "%s/pushloghtml?changeset=%s" % (
                self.found_repo, first_rev)
        return "%s/pushloghtml?fromchange=%s&tochange=%s" % (
            self.found_repo, first_rev, last_rev)

    def get_range(self):
        return self._reverse_if_find_fix(self.good_revision, self.bad_revision)

    def print_range(self):
        """
        Log the state of the current state of the bisection process, with an
        appropriate pushlog url.
        """
        words = self._reverse_if_find_fix('Last', 'First')
        self._logger.info("%s good revision: %s" % (words[0],
                                                    self.good_revision))
        self._logger.info("%s bad revision: %s" % (words[1],
                                                   self.bad_revision))
        self._logger.info("Pushlog:\n%s\n" % self.get_pushlog_url())

    def build_good(self, mid, new_data):
        """
        Called by the Bisector when a build is good.

        *new_data* is ensured to contain at least two elements.
        """
        self._print_progress(new_data)

    def build_bad(self, mid, new_data):
        """
        Called by the Bisector when a build is bad.

        *new_data* is ensured to contain at least two elements.
        """
        self._print_progress(new_data)

    def build_retry(self, mid):
        pass

    def build_skip(self, mid):
        pass

    def no_data(self):
        pass

    def finished(self):
        pass

    def user_exit(self, mid):
        pass


class NightlyHandler(BisectorHandler):
    build_data_class = NightlyBuildData
    good_date = None
    bad_date = None

    def initialize(self):
        BisectorHandler.initialize(self)
        # register dates
        self.good_date, self.bad_date = \
            self._reverse_if_find_fix(self.build_data.get_associated_data(0),
                                      self.build_data.get_associated_data(-1))

    def _print_progress(self, new_data):
        next_good_date = new_data.get_associated_data(0)
        next_bad_date = new_data.get_associated_data(-1)
        next_days_range = abs((next_bad_date - next_good_date).days)
        self._logger.info("Narrowed nightly regression window from"
                          " [%s, %s] (%d days) to [%s, %s] (%d days)"
                          " (~%d steps left)"
                          % (self.good_date,
                             self.bad_date,
                             abs((self.bad_date - self.good_date).days),
                             next_good_date,
                             next_bad_date,
                             next_days_range,
                             compute_steps_left(next_days_range)))

    def _print_date_range(self):
        words = self._reverse_if_find_fix('Newest', 'Oldest')
        self._logger.info('%s known good nightly: %s' % (words[0],
                                                         self.good_date))
        self._logger.info('%s known bad nightly: %s' % (words[1],
                                                        self.bad_date))

    def user_exit(self, mid):
        self._print_date_range()

    def are_revisions_available(self):
        return self.good_revision is not None and self.bad_revision is not None

    def get_date_range(self):
        return self._reverse_if_find_fix(self.good_date, self.bad_date)

    def print_range(self):
        if self.found_repo is None:
            # this may happen if we are bisecting old builds without
            # enough tests of the builds.
            self._logger.error("Sorry, but mozregression was unable to get"
                               " a repository - no pushlog url available.")
            # still we can print date range
            self._print_date_range()
        elif self.are_revisions_available():
            BisectorHandler.print_range(self)
        else:
            self._print_date_range()
            self._logger.info("Pushlog:\n%s\n" % self.get_pushlog_url())

    def get_pushlog_url(self):
        assert self.found_repo
        if self.are_revisions_available():
            return BisectorHandler.get_pushlog_url(self)
        else:
            # this must never happen, as we must have changesets
            # if we have the repo. But let's be paranoid, and this is a good
            # fallback
            start, end = self.get_date_range()
            return ("%s/pushloghtml?startdate=%s&enddate=%s\n"
                    % (self.found_repo, start, end))

    def find_inbound_changesets(self, days_required=4):
        self._logger.info("... attempting to bisect inbound builds (starting"
                          " from %d days prior, to make sure no inbound"
                          " revision is missed)" % days_required)
        infos = None
        days = days_required - 1
        too_many_attempts = False
        max_attempts = 3
        first_date = min(self.good_date, self.bad_date)
        while not infos or not infos.changeset:
            days += 1
            if days >= days_required + max_attempts:
                too_many_attempts = True
                break
            prev_date = first_date - datetime.timedelta(days=days)
            build_data = self.build_data
            infos = build_data.get_build_infos_for_date(prev_date)
        if days > days_required and not too_many_attempts:
            self._logger.info("At least one build folder was invalid, we have"
                              " to start from %d days ago." % days)

        if not self.find_fix:
            good_rev = infos.changeset
            bad_rev = self.bad_revision
        else:
            good_rev = self.good_revision
            bad_rev = infos.changeset
        if bad_rev is None or good_rev is None:
            # we cannot find valid nightly builds in the searched range.
            # two possible causes:
            # - old nightly builds do not have the changeset information
            #   so we can't go on inbound. Anyway, these are probably too
            #   old and won't even exists on inbound.
            # - something else (builds were not updated on archive.mozilla.org,
            #   or all invalid)
            start_range = first_date - datetime.timedelta(days=days_required)
            end_range = start_range - datetime.timedelta(days=max_attempts)
            raise MozRegressionError(
                "Not enough changeset information to produce initial inbound"
                " regression range (failed to find metadata between %s and %s)"
                ". Nightly build folders are invalids or too old in this"
                " range." % (start_range, end_range))

        return good_rev, bad_rev


class InboundHandler(BisectorHandler):
    build_data_class = InboundBuildData

    def _print_progress(self, new_data):
        self._logger.info("Narrowed inbound regression window from [%s, %s]"
                          " (%d revisions) to [%s, %s] (%d revisions)"
                          " (~%d steps left)"
                          % (self.build_data[0].short_changeset,
                             self.build_data[-1].short_changeset,
                             len(self.build_data),
                             new_data[0].short_changeset,
                             new_data[-1].short_changeset,
                             len(new_data),
                             compute_steps_left(len(new_data))))

    def user_exit(self, mid):
        words = self._reverse_if_find_fix('Newest', 'Oldest')
        self._logger.info('%s known good inbound revision: %s'
                          % (words[0], self.good_revision))
        self._logger.info('%s known bad inbound revision: %s'
                          % (words[1], self.bad_revision))


class Bisection(object):
    RUNNING = 0
    NO_DATA = 1
    FINISHED = 2
    USER_EXIT = 3

    def __init__(self, handler, build_data, download_manager, test_runner,
                 fetch_config, dl_in_background=True):
        self.handler = handler
        self.build_data = build_data
        self.download_manager = download_manager
        self.test_runner = test_runner
        self.fetch_config = fetch_config
        self.dl_in_background = dl_in_background
        self.previous_data = []

    def search_mid_point(self):
        self.handler.set_build_data(self.build_data)
        return self._search_mid_point()

    def _search_mid_point(self):
        return self.build_data.mid_point()

    def init_handler(self, mid_point):
        if len(self.build_data) == 0:
            self.handler.no_data()
            return self.NO_DATA

        self.handler.initialize()

        if mid_point == 0:
            self.handler.finished()
            return self.FINISHED
        return self.RUNNING

    def download_build(self, mid_point):
        """
        Download the build for the given mid_point.

        This call may start the download of next builds in background (if
        dl_in_background evaluates to True). Note that the mid point may
        change in this case.

        Returns a couple (new_mid_point, build_infos) where build_infos
        is the dict of build infos for the build.
        """
        build_infos = self.handler.build_data[mid_point]
        return self._download_build(mid_point, build_infos)

    def _download_build(self, mid_point, build_infos):
        dest = self.download_manager.focus_download(build_infos)
        build_infos.build_file = dest
        if self.dl_in_background:
            mid_point = self._download_next_builds(mid_point)
        return mid_point, build_infos

    def _download_next_builds(self, mid_point):
        # start downloading the next builds.
        # note that we don't have to worry if builds are already
        # downloaded, or if our build infos are the same because
        # this will be handled by the downloadmanager.
        def start_dl(r):
            # first get the next mid point
            # this will trigger some blocking downloads
            # (we need to find the build info)
            m = r.mid_point()
            if len(r) != 0:
                # this is a trick to call build_infos
                # with the the appropriate build_data
                self.handler.set_build_data(r)
                try:
                    # non-blocking download of the build
                    self.download_manager.download_in_background(
                        self.handler.build_data[m]
                    )
                finally:
                    # put the real build_data back
                    self.handler.set_build_data(self.build_data)
        bdata = self.build_data[mid_point]
        # download next left mid point
        start_dl(self.build_data[mid_point:])
        # download right next mid point
        start_dl(self.build_data[:mid_point+1])
        # since we called mid_point() on copy of self.build_data instance,
        # the underlying cache may have changed and we need to find the new
        # mid point.
        self.build_data.filter_invalid_builds()
        return self.build_data.index_of(lambda k: k[0] == bdata)

    def evaluate(self, build_infos):
        return self.test_runner.evaluate(build_infos,
                                         allow_back=bool(self.previous_data))

    def handle_verdict(self, mid_point, verdict):
        if verdict == 'g':
            # if build is good and we are looking for a regression, we
            # have to split from
            # [G, ?, ?, G, ?, B]
            # to
            #          [G, ?, B]
            self.previous_data.append(self.build_data)
            if not self.handler.find_fix:
                self.build_data = self.build_data[mid_point:]
            else:
                self.build_data = self.build_data[:mid_point+1]
            self.handler.build_good(mid_point, self.build_data)
        elif verdict == 'b':
            # if build is bad and we are looking for a regression, we
            # have to split from
            # [G, ?, ?, B, ?, B]
            # to
            # [G, ?, ?, B]
            self.previous_data.append(self.build_data)
            if not self.handler.find_fix:
                self.build_data = self.build_data[:mid_point+1]
            else:
                self.build_data = self.build_data[mid_point:]
            self.handler.build_bad(mid_point, self.build_data)
        elif verdict == 'r':
            self.handler.build_retry(mid_point)
        elif verdict == 's':
            self.handler.build_skip(mid_point)
            self.previous_data.append(self.build_data)
            self.build_data = self.build_data.deleted(mid_point)
        elif verdict == 'back':
            self.build_data = self.previous_data.pop(-1)
        else:
            # user exit
            self.handler.user_exit(mid_point)
            return self.USER_EXIT
        return self.RUNNING


class Bisector(object):
    """
    Handle the logic of the bisection process, and report events to a given
    :class:`BisectorHandler`.
    """
    def __init__(self, fetch_config, test_runner, download_manager,
                 dl_in_background=True):
        self.fetch_config = fetch_config
        self.test_runner = test_runner
        self.download_manager = download_manager
        self.dl_in_background = dl_in_background

    def bisect(self, handler, good, bad, **kwargs):
        if handler.find_fix:
            good, bad = bad, good
        build_data = handler.build_data_class(self.fetch_config,
                                              good,
                                              bad,
                                              **kwargs)

        return self._bisect(handler, build_data)

    def _bisect(self, handler, build_data):
        """
        Starts a bisection for a :class:`mozregression.build_data.BuildData`.
        """
        logger = handler._logger

        bisection = Bisection(handler, build_data, self.download_manager,
                              self.test_runner, self.fetch_config,
                              dl_in_background=self.dl_in_background)

        previous_verdict, previous_build_infos = None, None

        while True:
            mid = bisection.search_mid_point()
            result = bisection.init_handler(mid)
            if result != bisection.RUNNING:
                return result
            if previous_verdict == 'r':
                # if the last verdict was retry, do not download
                # the build. Futhermore trying to download if we are
                # in background download mode would stop the next builds
                # downloads.
                build_infos = previous_build_infos
            else:
                mid, build_infos = bisection.download_build(mid)
            try:
                verdict, app_info = bisection.evaluate(build_infos)
            except LauncherError, exc:
                # we got an unrecoverable error while trying
                # to run the tested app. We can just fallback
                # to skip the build.
                logger.info("Error: %s. Skipping this build..." % exc)
                verdict, app_info = 's', {}
            previous_verdict = verdict
            previous_build_infos = build_infos
            bisection.build_data[mid].update_from_app_info(app_info)
            result = bisection.handle_verdict(mid, verdict)
            if result != bisection.RUNNING:
                return result
