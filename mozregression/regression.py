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
from mozregression.utils import get_date, date_of_release, format_date
from mozregression.runnightly import NightlyRunner, parse_bits
from mozregression.runinbound import InboundRunner
from mozregression.inboundfinder import get_repo_url


def compute_steps_left(steps):
    if steps <= 1:
        return 0
    return math.trunc(math.log(steps, 2))


class Bisector(object):

    curr_date = ''
    found_repo = None

    def __init__(self, nightly_runner, inbound_runner, appname="firefox",
                 last_good_revision=None, first_bad_revision=None):
        self.nightly_runner = nightly_runner
        self.inbound_runner = inbound_runner
        self.appname = appname
        self.last_good_revision = last_good_revision
        self.first_bad_revision = first_bad_revision
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

        if self.appname == "firefox":
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

    def _ensure_metadata(self, good_date, bad_date):
        self._logger.info("Ensuring we have enough metadata to get a pushlog...")
        if not self.last_good_revision:
            self.found_repo, self.last_good_revision = \
                self.nightly_runner.get_build_info(good_date)

        if not self.first_bad_revision:
            self.found_repo, self.first_bad_revision = \
                self.nightly_runner.get_build_info(bad_date)

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
        self.found_repo = get_repo_url(
            inbound_branch=self.inbound_runner.inbound_branch)

        if not inbound_revisions:
            self._logger.info("Getting inbound builds between %s and %s"
                              % (self.last_good_revision,
                                 self.first_bad_revision))
            # anything within twelve hours is potentially within the range
            # (should be a tighter but some older builds have wrong timestamps,
            # see https://bugzilla.mozilla.org/show_bug.cgi?id=1018907 ...
            # we can change this at some point in the future, after those builds
            # expire)
            inbound_revisions = self.inbound_runner.app.build_finder \
                .get_build_infos(self.last_good_revision,
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
        self.inbound_runner.start(inbound_revisions[mid]['timestamp'])

        verdict = self._get_verdict('inbound', offer_skip=False)
        self.inbound_runner.stop()
        info = self.inbound_runner.get_app_info()
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
            self.inbound_runner.print_resume_info(self.last_good_revision,
                                                  self.first_bad_revision)
            return

        if len(inbound_revisions) > 1 and verdict in ('g', 'b'):
            if verdict == 'g':
                revisions_left = inbound_revisions[(mid+1):]
            else:
                revisions_left = inbound_revisions[:mid]
            revisions_left.ensure_limits()
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

    def bisect_nightlies(self, good_date, bad_date, skips=0):
        mid_date = good_date + (bad_date - good_date) / 2

        mid_date += datetime.timedelta(days=skips)

        if mid_date == bad_date or mid_date == good_date:
            self._logger.info("Got as far as we can go bisecting nightlies...")
            self._ensure_metadata(good_date, bad_date)
            self.print_range(good_date, bad_date)
            if self.appname in ('firefox', 'fennec', 'b2g'):
                self._logger.info("... attempting to bisect inbound builds"
                                  " (starting from previous week, to make"
                                  " sure no inbound revision is missed)")
                prev_date = good_date - datetime.timedelta(days=7)
                _, self.last_good_revision = \
                    self.nightly_runner.get_build_info(prev_date)
                self.bisect_inbound()
                return
            else:
                self._logger.info("(no more options with %s)" % self.appname)
                sys.exit()

        info = None
        while 1:
            self._logger.info("Running nightly for %s" % mid_date)
            if self.nightly_runner.start(mid_date):
                info = self.nightly_runner.get_app_info()
                self.found_repo = info['application_repository']
                if mid_date == bad_date:
                    self.print_range(good_date, bad_date)
                break
            else:
                if mid_date == bad_date:
                    sys.exit("Unable to get valid builds within the given"
                             " range. You should try to launch mozregression"
                             " again with a larger date range.")
            mid_date += datetime.timedelta(days=1)

        self.prev_date = self.curr_date
        self.curr_date = mid_date

        verdict = self._get_verdict('nightly')
        self.nightly_runner.stop()
        if verdict == 'g':
            self.last_good_revision = info['application_changeset']
            self.print_nightly_regression_progress(good_date, bad_date,
                                                   mid_date, bad_date)
            self.bisect_nightlies(mid_date, bad_date)
        elif verdict == 'b':
            self.first_bad_revision = info['application_changeset']
            self.print_nightly_regression_progress(good_date, bad_date,
                                                   good_date, mid_date)
            self.bisect_nightlies(good_date, mid_date)
        elif verdict == 's':
            # skip -- go 1 day further down
            self.bisect_nightlies(good_date, bad_date, skips=skips+1)
        elif verdict == 'e':
            self.nightly_runner.stop()
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
            self.nightly_runner.print_resume_info(good_date_string,
                                                  bad_date_string)
            return
        else:
            # retry -- since we're just calling ourselves with the same
            # parameters, it does the same thing again
            self.bisect_nightlies(good_date, bad_date)

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

    parser.add_argument("--inbound-branch",
                        metavar="[tracemonkey|mozilla-1.9.2]",
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

    inbound_runner = None
    if options.app in ("firefox", "fennec", "b2g"):
        inbound_runner = InboundRunner(appname=options.app,
                                       addons=options.addons,
                                       inbound_branch=options.inbound_branch,
                                       profile=options.profile,
                                       cmdargs=options.cmdargs,
                                       bits=options.bits,
                                       persist=options.persist)

    if options.inbound:
        if not options.last_good_revision or not options.first_bad_revision:
            sys.exit("If bisecting inbound, both --good-rev and --bad-rev"
                     " must be set")
        bisector = Bisector(None, inbound_runner, appname=options.app,
                            last_good_revision=options.last_good_revision,
                            first_bad_revision=options.first_bad_revision)
        app = bisector.bisect_inbound
    else:
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

        nightly_runner = NightlyRunner(appname=options.app, addons=options.addons,
                                       inbound_branch=options.inbound_branch,
                                       profile=options.profile,
                                       cmdargs=options.cmdargs,
                                       bits=options.bits,
                                       persist=options.persist)
        bisector = Bisector(nightly_runner, inbound_runner,
                            appname=options.app)
        app = lambda: bisector.bisect_nightlies(get_date(options.good_date),
                                                get_date(options.bad_date))
    try:
        app()
    except KeyboardInterrupt:
        sys.exit("\nInterrupted.")
    except errors.MozRegressionError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    cli()
