#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import math
import sys
import datetime
from mozlog.structured import get_default_logger
from mozregression.launchers import create_launcher
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

    def __init__(self, fetch_config, persist=None, launcher_kwargs=None):
        self.fetch_config = fetch_config
        self.persist = persist
        self.launcher_kwargs = launcher_kwargs or {}
        self.found_repo = None
        self.build_data = None
        self.last_good_revision = None
        self.first_bad_revision = None
        self.found_repo = None
        self.app_info = None
        self._logger = get_default_logger('Bisector')

    def set_build_data(self, build_data):
        """
        Save a reference of the :class:`mozregression.build_data.BuildData`
        instance.

        This is called by the bisector before each step of the bisection
        process.
        """
        self.build_data = build_data

    def launcher_persist_prefix(self, index):
        """
        Returns an appropriate prefix for a downloaded build.
        """
        raise NotImplementedError

    def _print_progress(self, new_data):
        """
        Log the current state of the bisection process.
        """
        raise NotImplementedError

    def start_launcher(self, index):
        """
        Create and returns a :class:`mozregression.launchers.Launcher`
        that has been started.

        This is called by the bisector when a build needs to be tested.
        """
        build_url = self.build_data[index]['build_url']
        launcher = create_launcher(self.fetch_config.app_name,
                                   build_url,
                                   persist=self.persist,
                                   persist_prefix=self.launcher_persist_prefix(index))
        launcher.start(**self.launcher_kwargs)
        self.app_info = launcher.get_app_info()
        self.found_repo = self.app_info['application_repository']
        return launcher

    def get_pushlog_url(self):
        return "%s/pushloghtml?fromchange=%s&tochange=%s" % (
            self.found_repo, self.last_good_revision, self.first_bad_revision)

    def _get_str_range(self):
        return ('revision: %s' % self.last_good_revision,
                'revision: %s' % self.first_bad_revision)

    def print_range(self):
        """
        Log the state of the current state of the bisection process, with an
        appropriate pushlog url.
        """
        good, bad = self._get_str_range()
        self._logger.info("Last good %s" % good)
        self._logger.info("First bad %s" % bad)
        self._logger.info("Pushlog:\n%s\n" % self.get_pushlog_url())

    def build_good(self, mid, new_data):
        """
        Called by the Bisector when a build is good.
        """
        self.last_good_revision = self.app_info['application_changeset']
        if len(new_data) > 1:
            self._print_progress(new_data)

    def build_bad(self, mid, new_data):
        """
        Called by the Bisector when a build is bad.
        """
        self.first_bad_revision = self.app_info['application_changeset']
        if len(new_data) > 1:
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
    build_type = 'nightly'
    good_date = None
    bad_date = None
    mid_date = None

    def launcher_persist_prefix(self, index):
        return '%s--%s--' % (self.mid_date,
                             self.fetch_config.get_nightly_repo(self.mid_date))

    def start_launcher(self, mid):
        # register dates
        self.good_date = self.build_data.get_date_for_index(0)
        self.bad_date = self.build_data.get_date_for_index(-1)
        self.mid_date = self.build_data.get_date_for_index(mid)
        self._logger.info("Running nightly for %s" % self.mid_date)
        return BisectorHandler.start_launcher(self, mid)

    def _print_progress(self, new_data):
        next_good_date = new_data.get_date_for_index(0)
        next_bad_date = new_data.get_date_for_index(-1)
        next_days_range = (next_bad_date - next_good_date).days
        self._logger.info("Narrowed nightly regression window from"
                          " [%s, %s] (%d days) to [%s, %s] (%d days)"
                          " (~%d steps left)"
                          % (self.good_date,
                             self.bad_date,
                             (self.bad_date - self.good_date).days,
                             next_good_date,
                             next_bad_date,
                             next_days_range,
                             compute_steps_left(next_days_range)))

    def ensure_metadata(self):
        if not self.last_good_revision:
            date = self.build_data.get_date_for_index(0)
            infos = self.build_data.get_build_infos_for_date(date)
            self.found_repo = infos['repository']
            self.last_good_revision = infos['changeset']

        if not self.first_bad_revision:
            date = self.build_data.get_date_for_index(-1)
            infos = self.build_data.get_build_infos_for_date(date)
            self.found_repo = infos['repository']
            self.first_bad_revision = infos['changeset']

    def _get_str_range(self):
        good, bad = BisectorHandler._get_str_range(self)
        good += ' (%s)' % self.good_date
        bad += ' (%s)' % self.bad_date
        return good, bad

class InboundHandler(BisectorHandler):
    build_type = 'inbound'

    def launcher_persist_prefix(self, index):
        return '%s--%s--' % (self.build_data[index]['timestamp'],
                             self.fetch_config.inbound_branch)

    def start_launcher(self, mid):
        data = self.build_data[mid]
        self._logger.info("Testing inbound build with timestamp %s,"
                          " revision %s"
                          % (data['timestamp'],
                             data['revision']))
        return BisectorHandler.start_launcher(self, mid)

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

class Bisector(object):
    """
    Handle the logic of the bisection process, and report events to a given
    :class:`BisectorHandler`.
    """
    NO_DATA = 1
    FINISHED = 2
    USER_EXIT = 3

    def __init__(self, handler):
        self.handler = handler

    def get_verdict(self, offer_skip=True):
        options = ['good', 'bad']
        if offer_skip:
            options.append('skip')
        options += ['retry', 'exit']
        # allow user to just type one letter
        allowed_inputs = options + [o[0] for o in options]
        # format options to nice printing
        formatted_options = (', '.join(["'%s'" % o for o in options[:-1]])
                             + " or '%s'" % options[-1])
        verdict = ""
        while verdict not in allowed_inputs:
            verdict = raw_input("Was this %s build good, bad, or broken?"
                                " (type %s and press Enter): "
                                % (self.handler.build_type,
                                   formatted_options))

        # shorten verdict to one character for processing...
        return verdict[0]

    def bisect(self, build_data):
        """
        Starts a bisection for a :class:`mozregression.build_data.BuildData`.
        """
        while True:
            self.handler.set_build_data(build_data)
            mid = build_data.mid_point()

            if len(build_data) == 0:
                self.handler.no_data()
                return self.NO_DATA

            if mid == 0:
                self.handler.finished()
                return self.FINISHED

            launcher = self.handler.start_launcher(mid)
            verdict = self.get_verdict()
            launcher.stop()

            if verdict == 'g':
                # if build is good, we have to split from
                # [G, ?, ?, G, ?, B]
                # to
                #          [G, ?, B]
                build_data = build_data[mid:]
                build_data.ensure_limits()
                self.handler.build_good(mid, build_data)
            elif verdict == 'b':
                # if build is bad, we have to split from
                # [G, ?, ?, B, ?, B]
                # to
                # [G, ?, ?, B]
                build_data = build_data[:mid+1]
                build_data.ensure_limits()
                self.handler.build_bad(mid, build_data)
            elif verdict == 'r':
                self.handler.build_retry(mid)
            elif verdict == 's':
                self.handler.build_skip(mid)
                del build_data[mid]
            else:
                # user exit
                self.handler.user_exit(mid)
                return self.USER_EXIT

class BisectRunner(object):
    def __init__(self, fetch_config, options):
        self.fetch_config = fetch_config
        self.options = options
        self.launcher_kwargs = dict(
            addons=options.addons,
            profile=options.profile,
            cmdargs=options.cmdargs,
        )
        self._logger = get_default_logger('Bisector')

    def bisect_nightlies(self, good_date, bad_date):
        build_data = NightlyBuildData(good_date, bad_date, self.fetch_config)
        handler = NightlyHandler(self.fetch_config,
                                 persist=self.options.persist,
                                 launcher_kwargs=self.launcher_kwargs)
        bisector = Bisector(handler)
        result = bisector.bisect(build_data)
        if result == Bisector.FINISHED:
            self._logger.info("Got as far as we can go bisecting nightlies...")
            self._logger.info("Ensuring we have enough metadata to get a pushlog...")
            handler.ensure_metadata()
            handler.print_range()
            if self.fetch_config.can_go_inbound():
                self._logger.info("... attempting to bisect inbound builds"
                                  " (starting from previous week, to make"
                                  " sure no inbound revision is missed)")
                infos = {}
                days = 6
                while not 'changeset' in infos:
                    days += 1
                    prev_date = good_date - datetime.timedelta(days=days)
                    infos = handler.build_data.get_build_infos_for_date(prev_date)
                if days > 7:
                    self._logger.info("At least one build folder was"
                                      " invalid, we have to start from"
                                      " %d days ago." % days)
                return self.bisect_inbound(infos['changeset'],
                                           handler.first_bad_revision)
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
            self._logger.info('Newest known good nightly: %s'
                              % handler.good_date)
            self._logger.info('Oldest known bad nightly: %s'
                              % handler.bad_date)
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
        inbound_data = InboundBuildData(self.fetch_config,
                                        good_rev,
                                        bad_rev,
                                        range=60*60*12)
        handler = InboundHandler(self.fetch_config,
                                 persist=self.options.persist,
                                 launcher_kwargs=self.launcher_kwargs)
        handler.last_good_revision = good_rev
        handler.first_bad_revision = bad_rev
        bisector = Bisector(handler)
        result = bisector.bisect(inbound_data)
        if result == Bisector.FINISHED:
            self._logger.info("Oh noes, no (more) inbound revisions :(")
            handler.print_range()
            self.offer_build(handler.last_good_revision,
                             handler.first_bad_revision)
        elif result == Bisector.USER_EXIT:
            self._logger.info('Newest known good inbound revision: %s'
                              % handler.last_good_revision)
            self._logger.info('Oldest known bad inbound revision: %s'
                              % handler.first_bad_revision)

            self.print_resume_info(handler)
        else:
            # NO_DATA
            self._logger.info("No inbound data found.")
            return 1
        return 0

    def print_resume_info(self, handler):
        if isinstance(handler, NightlyHandler):
            info = '--good=%s --bad=%s' % (handler.good_date, handler.bad_date)
        else:
            info = ('--inbound --good-rev=%s --bad-rev=%s'
                    % (handler.last_good_revision, handler.first_bad_revision))
        options = self.options
        info += ' --app=%s' % options.app
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

    def find_regression_chset(self, last_good_revision, first_bad_revision):
        # Uses mozcommitbuilder to bisect on changesets
        # Only needed if they want to bisect, so we'll put the dependency here.
        from mozcommitbuilder import builder
        commit_builder = builder.Builder()

        self._logger.info(" Narrowed changeset range from %s to %s"
                          % (last_good_revision, first_bad_revision))

        self._logger.info("Time to do some bisecting and building!")
        commit_builder.bisect(last_good_revision, first_bad_revision)
        quit()

    def offer_build(self, last_good_revision, first_bad_revision):
        verdict = raw_input("do you want to bisect further by fetching"
                            " the repository and building? (y or n) ")
        if verdict != "y":
            sys.exit()

        if self.fetch_config.app_name == "firefox":
            self.find_regression_chset(last_good_revision, first_bad_revision)
        else:
            sys.exit("Bisection on anything other than firefox is not"
                     " currently supported.")
