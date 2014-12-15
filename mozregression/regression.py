#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import mozinfo
import sys
import math
from argparse import ArgumentParser
from mozlog.structured import commandline, get_default_logger

from mozregression import errors
from mozregression import __version__
from mozregression.utils import (parse_date, date_of_release, format_date,
                                 parse_bits)
from mozregression.inboundfinder import get_repo_url, BuildsFinder
from mozregression.build_data import NightlyBuildData
from mozregression.fetch_configs import create_config
from mozregression.launchers import create_launcher

def compute_steps_left(steps):
    if steps <= 1:
        return 0
    return math.trunc(math.log(steps, 2))


class Bisector(object):

    curr_date = ''
    found_repo = None

    def __init__(self, fetch_config, options,
                 last_good_revision=None, first_bad_revision=None):
        self.last_good_revision = last_good_revision
        self.first_bad_revision = first_bad_revision
        self.fetch_config = fetch_config
        self.options = options
        self.launcher_kwargs = dict(
            addons=options.addons,
            profile=options.profile,
            cmdargs=options.cmdargs,
        )
        self.nightly_data = NightlyBuildData(parse_date(options.good_date),
                                             parse_date(options.bad_date),
                                             fetch_config)
        self._logger = get_default_logger('Bisector')

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

    def print_range(self, good_date=None, bad_date=None):
        def _print_date_revision(name, revision, date):
            if date and revision:
                self._logger.info("%s revision: %s (%s)"
                                  % (name, revision, date))
            elif revision:
                self._logger.info("%s revision: %s" % (name, revision))
            elif date:
                self._logger.info("%s build: %s" % (name, date))
        _print_date_revision("Last good", self.last_good_revision, good_date)
        _print_date_revision("First bad", self.first_bad_revision, bad_date)

        self._logger.info("Pushlog:\n%s\n"
                          % self.get_pushlog_url(good_date, bad_date))

    def _ensure_metadata(self):
        self._logger.info("Ensuring we have enough metadata to get a pushlog...")
        if not self.last_good_revision:
            url = self.nightly_data[0]['build_txt_url']
            infos = self.nightly_data.info_fetcher.find_build_info_txt(url)
            self.found_repo = infos['repository']
            self.last_good_revision = infos['changeset']

        if not self.first_bad_revision:
            url = self.nightly_data[-1]['build_txt_url']
            infos = self.nightly_data.info_fetcher.find_build_info_txt(url)
            self.found_repo = infos['repository']
            self.first_bad_revision = infos['changeset']

    def _get_verdict(self, build_type, offer_skip=True):
        verdict = ""
        options = ['good', 'g', 'bad', 'b', 'retry', 'r']
        if offer_skip:
            options += ['skip', 's']
        options += ['exit']
        while verdict not in options:
            verdict = raw_input("Was this %s build good, bad, or broken?"
                                " (type 'good', 'bad', 'skip', 'retry', or"
                                " 'exit' and press Enter): " % build_type)

        # shorten verdict to one character for processing...
        if len(verdict) > 1:
            return verdict[0]

        return verdict

    def print_inbound_regression_progress(self, revisions, revisions_left):
        self._logger.info("Narrowed inbound regression window from [%s, %s]"
                          " (%d revisions) to [%s, %s] (%d revisions)"
                          " (~%d steps left)"
                          % (revisions[0]['revision'],
                             revisions[-1]['revision'],
                             len(revisions),
                             revisions_left[0]['revision'],
                             revisions_left[-1]['revision'],
                             len(revisions_left),
                             compute_steps_left(len(revisions_left))))

    def bisect_inbound(self, inbound_revisions=None):
        self.found_repo = get_repo_url(inbound_branch=self.fetch_config.inbound_branch)

        if inbound_revisions is None:
            self._logger.info("Getting inbound builds between %s and %s"
                              % (self.last_good_revision,
                                 self.first_bad_revision))
            # anything within twelve hours is potentially within the range
            # (should be a tighter but some older builds have wrong timestamps,
            # see https://bugzilla.mozilla.org/show_bug.cgi?id=1018907 ...
            # we can change this at some point in the future, after those builds
            # expire)
            build_finder = BuildsFinder(self.fetch_config)
            inbound_revisions = build_finder.get_build_infos(self.last_good_revision,
                                                             self.first_bad_revision,
                                                             range=60*60*12)

        mid = inbound_revisions.mid_point()
        if mid == 0:
            self._logger.info("Oh noes, no (more) inbound revisions :(")
            self.print_range()
            self.offer_build(self.last_good_revision,
                             self.first_bad_revision)
            return
        # hardcode repo to mozilla-central (if we use inbound, we may be
        # missing some revisions that went into the nightlies which we may
        # also be comparing against...)

        self._logger.info("Testing inbound build with timestamp %s,"
                          " revision %s"
                          % (inbound_revisions[mid]['timestamp'],
                             inbound_revisions[mid]['revision']))
        build_url = inbound_revisions[mid]['build_url']
        persist_prefix='%s-%s-' % (inbound_revisions[mid]['timestamp'],
                                   self.fetch_config.inbound_branch)
        launcher = create_launcher(self.fetch_config.app_name,
                                   build_url,
                                   persist=self.options.persist,
                                   persist_prefix=persist_prefix)
        launcher.start()

        verdict = self._get_verdict('inbound', offer_skip=False)
        info = launcher.get_app_info()
        launcher.stop()
        if verdict == 'g':
            self.last_good_revision = info['application_changeset']
        elif verdict == 'b':
            self.first_bad_revision = info['application_changeset']
        elif verdict == 'r':
            # do the same thing over again
            self.bisect_inbound(inbound_revisions=inbound_revisions)
            return
        elif verdict == 'e':
            self._logger.info('Newest known good inbound revision: %s'
                              % self.last_good_revision)
            self._logger.info('Oldest known bad inbound revision: %s'
                              % self.first_bad_revision)

            self._logger.info('To resume, run:')
            self.print_inbound_resume_info(self.last_good_revision,
                                           self.first_bad_revision)
            return

        if len(inbound_revisions) > 1 and verdict in ('g', 'b'):
            if verdict == 'g':
                revisions_left = inbound_revisions[mid:]
            else:
                revisions_left = inbound_revisions[:mid]
            revisions_left.ensure_limits()
            if len(revisions_left) > 0:
                self.print_inbound_regression_progress(inbound_revisions,
                                                       revisions_left)
            self.bisect_inbound(revisions_left)
        else:
            # no more inbounds to be bisect, we must build
            self._logger.info("No more inbounds to bisect")
            self.print_range()
            self.offer_build(self.last_good_revision, self.first_bad_revision)

    def print_nightly_regression_progress(self, good_date, bad_date,
                                          next_good_date, next_bad_date):
        next_days_range = (next_bad_date - next_good_date).days
        self._logger.info("Narrowed nightly regression window from"
                          " [%s, %s] (%d days) to [%s, %s] (%d days)"
                          " (~%d steps left)"
                          % (format_date(good_date),
                             format_date(bad_date),
                             (bad_date - good_date).days,
                             format_date(next_good_date),
                             format_date(next_bad_date),
                             next_days_range,
                             compute_steps_left(next_days_range)))

    def bisect_nightlies(self):
        mid = self.nightly_data.mid_point()

        if len(self.nightly_data) == 0:
            sys.exit("Unable to get valid builds within the given"
                     " range. You should try to launch mozregression"
                     " again with a larger date range.")

        good_date = self.nightly_data.get_date_for_index(0)
        bad_date = self.nightly_data.get_date_for_index(-1)
        mid_date = self.nightly_data.get_date_for_index(mid)

        if mid_date == bad_date or mid_date == good_date:
            self._logger.info("Got as far as we can go bisecting nightlies...")
            self._ensure_metadata()
            self.print_range(good_date, bad_date)
            if self.fetch_config.can_go_inbound():
                self._logger.info("... attempting to bisect inbound builds"
                                  " (starting from previous week, to make"
                                  " sure no inbound revision is missed)")
                infos = {}
                days = 6
                while not 'changeset' in infos:
                    days += 1
                    prev_date = good_date - datetime.timedelta(days=days)
                    infos = self.nightly_data.get_build_infos_for_date(prev_date)
                if days > 7:
                    self._logger.info("At least one build folder was"
                                      " invalid, we have to start from"
                                      " %d days ago." % days)
                self.last_good_revision = infos['changeset']
                self.bisect_inbound()
                return
            else:
                message = ("Can not bissect inbound for application `%s`"
                           % self.fetch_config.app_name)
                if self.fetch_config.is_inbound():
                    # the config is able to bissect inbound but not
                    # for this repo.
                    message += (" because the repo `%s` was specified"
                                % self.options.repo)
                self._logger.info(message + '.')
                sys.exit()

        build_url = self.nightly_data[mid]['build_url']
        persist_prefix = ('%s-%s-'
                          % (mid_date,
                             self.fetch_config.get_nightly_repo(mid_date)))
        self._logger.info("Running nightly for %s" % mid_date)
        launcher = create_launcher(self.fetch_config.app_name,
                                   build_url,
                                   persist=self.options.persist,
                                   persist_prefix=persist_prefix)
        launcher.start(**self.launcher_kwargs)
        info = launcher.get_app_info()
        self.found_repo = info['application_repository']

        self.prev_date = self.curr_date
        self.curr_date = mid_date

        verdict = self._get_verdict('nightly')
        launcher.stop()
        if verdict == 'g':
            self.last_good_revision = info['application_changeset']
            self.print_nightly_regression_progress(good_date, bad_date,
                                                   mid_date, bad_date)
            self.nightly_data = self.nightly_data[mid:]
        elif verdict == 'b':
            self.first_bad_revision = info['application_changeset']
            self.print_nightly_regression_progress(good_date, bad_date,
                                                   good_date, mid_date)
            self.nightly_data = self.nightly_data[:mid]
        elif verdict == 's':
            del self.nightly_data[mid]
        elif verdict == 'e':
            good_date_string = '%04d-%02d-%02d' % (good_date.year,
                                                   good_date.month,
                                                   good_date.day)
            bad_date_string = '%04d-%02d-%02d' % (bad_date.year,
                                                  bad_date.month,
                                                  bad_date.day)
            self._logger.info('Newest known good nightly: %s'
                              % good_date_string)
            self._logger.info('Oldest known bad nightly: %s' % bad_date_string)
            self._logger.info('To resume, run:')
            self.print_nightly_resume_info(good_date_string,
                                           bad_date_string)
            return
        self.bisect_nightlies()

    def get_pushlog_url(self, good_date, bad_date):
        # if we don't have precise revisions, we need to resort to just
        # using handwavey dates
        if not self.last_good_revision or not self.first_bad_revision:
            # pushlogs are typically done with the oldest date first
            if good_date < bad_date:
                start = good_date
                end = bad_date
            else:
                start = bad_date
                end = good_date
            return "%s/pushloghtml?startdate=%s&enddate=%s" % (self.found_repo,
                                                               start, end)

        return "%s/pushloghtml?fromchange=%s&tochange=%s" % (
            self.found_repo, self.last_good_revision, self.first_bad_revision)

    def get_resume_options(self):
        info = ""
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
        return info

    def print_nightly_resume_info(self, good_date_string, bad_date_string):
        self._logger.info('mozregression --good=%s --bad=%s%s'
                          % (good_date_string,
                             bad_date_string,
                             self.get_resume_options()))

    def print_inbound_resume_info(self, last_good_revision, first_bad_revision):
        self._logger.info('mozregression --good-rev=%s --bad-rev=%s%s'
                          % (last_good_revision,
                             first_bad_revision,
                             self.get_resume_options()))

def parse_args():
    usage = ("\n"
             " %(prog)s [OPTIONS]"
             " [[--bad BAD_DATE]|[--bad-release BAD_RELEASE]]"
             " [[--good GOOD_DATE]|[--good-release GOOD_RELEASE]]"
             "\n"
             " %(prog)s [OPTIONS]"
             " --inbound --bad-rev BAD_REV --good-rev GOOD_REV")

    parser = ArgumentParser(usage=usage)
    parser.add_argument("--version", action="version", version=__version__,
                        help="print the mozregression version number and exits")

    parser.add_argument("-b", "--bad",
                        metavar="YYYY-MM-DD",
                        dest="bad_date",
                        help="first known bad nightly build, default is today")

    parser.add_argument("-g", "--good",
                        metavar="YYYY-MM-DD",
                        dest="good_date",
                        help="last known good nightly build")

    parser.add_argument("--bad-release",
                        type=int,
                        help=("first known bad nightly build. This option is"
                              " incompatible with --bad."))

    parser.add_argument("--good-release",
                        type=int,
                        help=("last known good nightly build. This option is"
                              " incompatible with --good."))

    parser.add_argument("--inbound",
                        action="store_true",
                        help=("use inbound instead of nightlies (use --good-rev"
                              " and --bad-rev options"))

    parser.add_argument("--bad-rev", dest="first_bad_revision",
                        help="first known bad revision (use with --inbound)")

    parser.add_argument("--good-rev", dest="last_good_revision",
                        help="last known good revision (use with --inbound)")

    parser.add_argument("-e", "--addon",
                        dest="addons",
                        action='append',
                        default=[],
                        metavar="PATH1",
                        help="an addon to install; repeat for multiple addons")

    parser.add_argument("-p", "--profile",
                        metavar="PATH",
                        help="profile to use with nightlies")

    parser.add_argument("-a", "--arg",
                        dest="cmdargs",
                        action='append',
                        default=[],
                        metavar="ARG1",
                        help=("a command-line argument to pass to the"
                              " application; repeat for multiple arguments"))

    parser.add_argument("-n", "--app",
                        choices=('firefox', 'fennec', 'thunderbird', 'b2g'),
                        default="firefox",
                        help="application name. Default: %(default)s")

    parser.add_argument("--repo",
                        metavar="[mozilla-aurora|mozilla-beta|...]",
                        help="repository name used for nightly hunting")

    parser.add_argument("--inbound-branch",
                        metavar="[b2g-inbound|fx-team|...]",
                        help="inbound branch name on ftp.mozilla.org")

    parser.add_argument("--bits",
                        choices=("32", "64"),
                        default=mozinfo.bits,
                        help=("force 32 or 64 bit version (only applies to"
                              " x86_64 boxes). Default: %(default)s bits"))

    parser.add_argument("--persist",
                        help="the directory in which files are to persist")

    commandline.add_logging_group(parser)
    options = parser.parse_args()
    options.bits = parse_bits(options.bits)
    return options


def cli():
    default_bad_date = str(datetime.date.today())
    default_good_date = "2009-01-01"
    options = parse_args()
    logger = commandline.setup_logging("mozregression", options, {"mach": sys.stdout})

    fetch_config = create_config(options.app, mozinfo.os, options.bits)

    if fetch_config.is_inbound():
        # this can be useful for both inbound and nightly, because we
        # can go to inbound from nightly.
        fetch_config.set_inbound_branch(options.inbound_branch)

    if options.inbound:
        if not fetch_config.is_inbound():
            sys.exit('Unable to bissect inbound for `%s`' % fetch_config.app_name)
        if not options.last_good_revision or not options.first_bad_revision:
            sys.exit("If bisecting inbound, both --good-rev and --bad-rev"
                     " must be set")
        bisector = Bisector(fetch_config, options,
                            last_good_revision=options.last_good_revision,
                            first_bad_revision=options.first_bad_revision)
        app = bisector.bisect_inbound
    else:
        # TODO: currently every fetch_config is nightly aware. Shoud we test
        # for this to be sure here ?
        fetch_config.set_nightly_repo(options.repo)
        if not options.bad_release and not options.bad_date:
            options.bad_date = default_bad_date
            logger.info("No 'bad' date specified, using %s" % options.bad_date)
        elif options.bad_release and options.bad_date:
            sys.exit("Options '--bad_release' and '--bad_date' are"
                     " incompatible.")
        elif options.bad_release:
            options.bad_date = date_of_release(options.bad_release)
            if options.bad_date is None:
                sys.exit("Unable to find a matching date for release "
                         + str(options.bad_release))
            logger.info("Using 'bad' date %s for release %s"
                        % (options.bad_date, options.bad_release))
        if not options.good_release and not options.good_date:
            options.good_date = default_good_date
            logger.info("No 'good' date specified, using %s"
                        % options.good_date)
        elif options.good_release and options.good_date:
            sys.exit("Options '--good_release' and '--good_date'"
                     " are incompatible.")
        elif options.good_release:
            options.good_date = date_of_release(options.good_release)
            if options.good_date is None:
                sys.exit("Unable to find a matching date for release "
                         + str(options.good_release))
            logger.info("Using 'good' date %s for release %s"
                        % (options.good_date, options.good_release))

        bisector = Bisector(fetch_config, options)
        app = bisector.bisect_nightlies
    try:
        app()
    except KeyboardInterrupt:
        sys.exit("\nInterrupted.")
    except errors.MozRegressionError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    cli()
