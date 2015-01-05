#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import math
import sys
import datetime
from mozlog.structured import get_default_logger

from mozregression.test_runner import ManualTestRunner
from mozregression.build_data import NightlyBuildData, InboundBuildData


def compute_steps_left(steps):
    if steps <= 1:
        return 0
    return math.trunc(math.log(steps, 2))

class BisectorHandler(object):
    """
    React to events of a :class:`Bisector`. This is intended to be subclassed.

    A BisectorHandler keep the state of the current bisection process.
    """
    build_type = 'unknown'

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

    def build_infos(self, index):
        """
        Compute build infos (a dict) when a build is about to be tested.
        """
        infos = {'build_type': self.build_type}
        infos.update(self.build_data[index])
        return infos

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
        self.found_repo = self.build_data[0]['repository']
        self.good_revision, self.bad_revision = \
            self._reverse_if_find_fix(self.build_data[0]['changeset'],
                                      self.build_data[-1]['changeset'])

    def get_pushlog_url(self):
        first_rev, last_rev = self._reverse_if_find_fix(self.good_revision,
                                                        self.bad_revision)
        return "%s/pushloghtml?fromchange=%s&tochange=%s" % (
            self.found_repo, first_rev, last_rev)

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
    build_type = 'nightly'
    good_date = None
    bad_date = None

    def initialize(self):
        BisectorHandler.initialize(self)
        # register dates
        self.good_date, self.bad_date = \
            self._reverse_if_find_fix(self.build_data.get_associated_data(0),
                                     self.build_data.get_associated_data(-1))

    def build_infos(self, index):
        infos = BisectorHandler.build_infos(self, index)
        infos['build_date'] = self.build_data.get_associated_data(index)
        return infos

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

    def user_exit(self, mid):
        words = self._reverse_if_find_fix('Newest', 'Oldest')
        self._logger.info('%s known good nightly: %s' % (words[0],
                                                         self.good_date))
        self._logger.info('%s known bad nightly: %s' % (words[1],
                                                        self.bad_date))

class InboundHandler(BisectorHandler):
    build_data_class = InboundBuildData
    build_type = 'inbound'

    def _print_progress(self, new_data):
        self._logger.info("Narrowed inbound regression window from [%s, %s]"
                          " (%d revisions) to [%s, %s] (%d revisions)"
                          " (~%d steps left)"
                          % (self.build_data[0]['revision'],
                             self.build_data[-1]['revision'],
                             len(self.build_data),
                             new_data[0]['revision'],
                             new_data[-1]['revision'],
                             len(new_data),
                             compute_steps_left(len(new_data))))

    def user_exit(self, mid):
        words = self._reverse_if_find_fix('Newest', 'Oldest')
        self._logger.info('%s known good inbound revision: %s'
                          % (words[0], self.good_revision))
        self._logger.info('%s known bad inbound revision: %s'
                          % (words[1], self.bad_revision))

class Bisector(object):
    """
    Handle the logic of the bisection process, and report events to a given
    :class:`BisectorHandler`.
    """
    NO_DATA = 1
    FINISHED = 2
    USER_EXIT = 3

    def __init__(self, fetch_config, test_runner):
        self.fetch_config = fetch_config
        self.test_runner = test_runner

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
        while True:
            handler.set_build_data(build_data)
            mid = build_data.mid_point()

            if len(build_data) == 0:
                handler.no_data()
                return self.NO_DATA

            handler.initialize()

            if mid == 0:
                handler.finished()
                return self.FINISHED

            build_infos = handler.build_infos(mid)
            verdict = self.test_runner.evaluate(build_infos)

            if verdict == 'g':
                # if build is good and we are looking for a regression, we
                # have to split from
                # [G, ?, ?, G, ?, B]
                # to
                #          [G, ?, B]
                if not handler.find_fix:
                    build_data = build_data[mid:]
                else:
                    build_data = build_data[:mid+1]
                handler.build_good(mid, build_data)
            elif verdict == 'b':
                # if build is bad and we are looking for a regression, we
                # have to split from
                # [G, ?, ?, B, ?, B]
                # to
                # [G, ?, ?, B]
                if not handler.find_fix:
                    build_data = build_data[:mid+1]
                else:
                    build_data = build_data[mid:]
                handler.build_bad(mid, build_data)
            elif verdict == 'r':
                handler.build_retry(mid)
            elif verdict == 's':
                handler.build_skip(mid)
                del build_data[mid]
            else:
                # user exit
                handler.user_exit(mid)
                return self.USER_EXIT

class BisectRunner(object):
    def __init__(self, fetch_config, options):
        self.fetch_config = fetch_config
        self.options = options
        launcher_kwargs = dict(
            addons=options.addons,
            profile=options.profile,
            cmdargs=options.cmdargs,
        )
        test_runner = ManualTestRunner(fetch_config,
                                       persist=options.persist,
                                       launcher_kwargs=launcher_kwargs)
        self.bisector = Bisector(fetch_config, test_runner)
        self._logger = get_default_logger('Bisector')

    def bisect_nightlies(self, good_date, bad_date):
        handler = NightlyHandler(find_fix=self.options.find_fix)
        result = self.bisector.bisect(handler, good_date, bad_date)
        if result == Bisector.FINISHED:
            self._logger.info("Got as far as we can go bisecting nightlies...")
            handler.print_range()
            if self.fetch_config.can_go_inbound():
                self._logger.info("... attempting to bisect inbound builds"
                                  " (starting from previous week, to make"
                                  " sure no inbound revision is missed)")
                infos = {}
                days = 6
                first_date = min(handler.good_date, handler.bad_date)
                while not 'changeset' in infos:
                    days += 1
                    prev_date = first_date - datetime.timedelta(days=days)
                    infos = handler.build_data.get_build_infos_for_date(prev_date)
                if days > 7:
                    self._logger.info("At least one build folder was"
                                      " invalid, we have to start from"
                                      " %d days ago." % days)

                if not handler.find_fix:
                    good_rev = infos['changeset']
                    bad_rev = handler.bad_revision
                else:
                    good_rev = handler.good_revision
                    bad_rev = infos['changeset']
                return self.bisect_inbound(good_rev, bad_rev)
            else:
                message = ("Can not bissect inbound for application `%s`"
                           % self.fetch_config.app_name)
                if self.fetch_config.is_inbound():
                    # the config is able to bissect inbound but not
                    # for this repo.
                    message += (" because the repo `%s` was specified"
                                % self.options.repo)
                self._logger.info(message + '.')
        elif result == Bisector.USER_EXIT:
            self.print_resume_info(handler)
        else:
            # NO_DATA
            self._logger.info("Unable to get valid builds within the given"
                              " range. You should try to launch mozregression"
                              " again with a larger date range.")
            return 1
        return 0

    def bisect_inbound(self, good_rev, bad_rev):
        self._logger.info("Getting inbound builds between %s and %s"
                          % (good_rev, bad_rev))
        # anything within twelve hours is potentially within the range
        # (should be a tighter but some older builds have wrong timestamps,
        # see https://bugzilla.mozilla.org/show_bug.cgi?id=1018907 ...
        # we can change this at some point in the future, after those builds
        # expire)
        handler = InboundHandler(find_fix=self.options.find_fix)
        result = self.bisector.bisect(handler, good_rev, bad_rev,
                                      range=60*60*12)
        if result == Bisector.FINISHED:
            self._logger.info("Oh noes, no (more) inbound revisions :(")
            handler.print_range()
        elif result == Bisector.USER_EXIT:
            self.print_resume_info(handler)
        else:
            # NO_DATA
            self._logger.info("No inbound data found.")
            # check if we have found revisions
            if handler.build_data.raw_revisions:
                # if we have, then these builds are probably too old
                self._logger.info('There are no build dirs on inbound for'
                                  ' these changesets.')
            return 1
        return 0

    def print_resume_info(self, handler):
        if isinstance(handler, NightlyHandler):
            info = '--good=%s --bad=%s' % (handler.good_date, handler.bad_date)
        else:
            info = ('--inbound --good-rev=%s --bad-rev=%s'
                    % (handler.good_revision, handler.bad_revision))
        options = self.options
        info += ' --app=%s' % options.app
        if options.find_fix:
            info += ' --find-fix'
        if len(options.addons) > 0:
            info += ' --addons=%s' % ",".join(options.addons)
        if options.profile is not None:
            info += ' --profile=%s' % options.profile
        if options.inbound_branch is not None:
            info += ' --inbound-branch=%s' % options.inbound_branch
        info += ' --bits=%s' % options.bits
        if options.persist is not None:
            info += ' --persist=%s' % options.persist

        self._logger.info('To resume, run:')
        self._logger.info('mozregression %s' % info)
