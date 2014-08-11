#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import mozinfo
import sys
from optparse import OptionParser

from mozregression.utils import get_date
from mozregression.runnightly import NightlyRunner, parse_bits
from mozregression.runinbound import InboundRunner


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

    def find_regression_chset(self, last_good_revision, first_bad_revision):
        # Uses mozcommitbuilder to bisect on changesets
        # Only needed if they want to bisect, so we'll put the dependency here.
        from mozcommitbuilder import builder
        commit_builder = builder.Builder()

        print "\n Narrowed changeset range from " + last_good_revision \
            + " to " + first_bad_revision + "\n"

        print "Time to do some bisecting and building!"
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
            print "Bisection on anything other than firefox is not" \
                  " currently supported."
            sys.exit()

    def print_range(self, good_date=None, bad_date=None):
        def _print_date_revision(name, revision, date):
            if date and revision:
                print "%s revision: %s (%s)" % (name, revision, date)
            elif revision:
                print "%s revision: %s" % (name, revision)
            elif date:
                print "%s build: %s" % (name, date)
        _print_date_revision("Last good", self.last_good_revision, good_date)
        _print_date_revision("First bad", self.first_bad_revision, bad_date)

        print "Pushlog:\n" + self.get_pushlog_url(good_date, bad_date) + "\n"

    def _ensure_metadata(self, good_date, bad_date):
        print "Ensuring we have enough metadata to get a pushlog..."
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

    def bisect_inbound(self, inbound_revisions=None):
        if not inbound_revisions:
            print "Getting inbound builds between %s and %s" % (
                self.last_good_revision, self.first_bad_revision)
            # anything within twelve hours is potentially within the range
            # (should be a tighter but some older builds have wrong timestamps,
            # see https://bugzilla.mozilla.org/show_bug.cgi?id=1018907 ...
            # we can change this at some point in the future, after those builds
            # expire)
            inbound_revisions = self.inbound_runner.app.build_finder \
                .get_build_infos(self.last_good_revision,
                                 self.first_bad_revision,
                                 range=60*60*12)

            if not inbound_revisions:
                print "Oh noes, no (more) inbound revisions :("
                self.offer_build(self.last_good_revision,
                                 self.first_bad_revision)
                return
        # hardcode repo to mozilla-central (if we use inbound, we may be
        # missing some revisions that went into the nightlies which we may
        # also be comparing against...)

        mid = len(inbound_revisions) / 2
        print "Testing inbound build with timestamp %s," \
              " revision %s" % (inbound_revisions[mid]['timestamp'],
                                inbound_revisions[mid]['revision'])
        self.inbound_runner.start(inbound_revisions[mid]['timestamp'])

        verdict = self._get_verdict('inbound', offer_skip=False)
        self.inbound_runner.stop()
        info = self.inbound_runner.get_app_info()
        self.found_repo = info['application_repository']
        if verdict == 'g':
            self.last_good_revision = info['application_changeset']
        elif verdict == 'b':
            self.first_bad_revision = info['application_changeset']
        elif verdict == 'r':
            # do the same thing over again
            self.bisect_inbound(inbound_revisions=inbound_revisions)
            return
        elif verdict == 'e':
            print 'Newest known good inbound revision: %s' \
                % self.last_good_revision
            print 'Oldest known bad inbound revision: %s' \
                % self.first_bad_revision

            print 'To resume, run:'
            self.inbound_runner.print_resume_info(self.last_good_revision,
                                                  self.first_bad_revision)
            return

        if len(inbound_revisions) > 1 and verdict == 'g':
            self.bisect_inbound(inbound_revisions[(mid+1):])
        elif len(inbound_revisions) > 1 and verdict == 'b':
            self.bisect_inbound(inbound_revisions[:mid])
        else:
            # no more inbounds to be bisect, we must build
            print "No more inbounds to bisect"
            self.print_range()
            self.offer_build(self.last_good_revision, self.first_bad_revision)

    def bisect_nightlies(self, good_date, bad_date, skips=0):
        mid_date = good_date + (bad_date - good_date) / 2

        mid_date += datetime.timedelta(days=skips)

        if mid_date == bad_date or mid_date == good_date:
            print "Got as far as we can go bisecting nightlies..."
            self._ensure_metadata(good_date, bad_date)
            self.print_range(good_date, bad_date)
            if self.appname in ('firefox', 'fennec', 'b2g'):
                print "... attempting to bisect inbound builds (starting " \
                    "from previous day, to make sure no inbound revision is " \
                    "missed)"
                prev_date = good_date - datetime.timedelta(days=1)
                _, self.last_good_revision = \
                    self.nightly_runner.get_build_info(prev_date)
                self.bisect_inbound()
                return
            else:
                print "(no more options with %s)" % self.appname
                sys.exit()

        info = None
        while 1:
            print "Running nightly for %s" % mid_date
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
            self.bisect_nightlies(mid_date, bad_date)
        elif verdict == 'b':
            self.first_bad_revision = info['application_changeset']
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
            print 'Newest known good nightly: %s' % good_date_string
            print 'Oldest known bad nightly: %s' % bad_date_string
            print 'To resume, run:'
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


def cli():
    parser = OptionParser()
    parser.add_option("-b", "--bad", dest="bad_date",
                      help="first known bad nightly build, default is today",
                      metavar="YYYY-MM-DD", default=str(datetime.date.today()))
    parser.add_option("-g", "--good", dest="good_date",
                      help="last known good nightly build",
                      metavar="YYYY-MM-DD", default=None)
    parser.add_option("-e", "--addon", dest="addons",
                      help="an addon to install; repeat for multiple addons",
                      metavar="PATH1", default=[], action="append")
    parser.add_option("-p", "--profile", dest="profile",
                      help="profile to use with nightlies", metavar="PATH")
    parser.add_option("-a", "--arg", dest="cmdargs",
                      help="a command-line argument to pass to the application;"
                           " repeat for multiple arguments",
                      metavar="ARG1", default=[], action="append")
    parser.add_option("-n", "--app", dest="app",
                      help="application name  (firefox, fennec,"
                      " thunderbird or b2g)",
                      metavar="[firefox|fennec|thunderbird|b2g]",
                      default="firefox")
    parser.add_option("-r", "--repo", dest="repo_name",
                      help="repository name on ftp.mozilla.org",
                      metavar="[tracemonkey|mozilla-1.9.2]", default=None)
    parser.add_option("--bits", dest="bits",
                      help="force 32 or 64 bit version (only applies to"
                      " x86_64 boxes)",
                      choices=("32", "64"), default=mozinfo.bits)
    parser.add_option("--persist", dest="persist",
                      help="the directory in which files are to persist ie."
                      " /Users/someuser/Documents")
    parser.add_option("--inbound", action="store_true", dest="inbound",
                      help="use inbound instead of nightlies (use --good-rev"
                      " and --bad-rev options")
    parser.add_option("--bad-rev", dest="first_bad_revision",
                      help="first known bad revision (use with --inbound)")
    parser.add_option("--good-rev", dest="last_good_revision",
                      help="last known good revision (use with --inbound)")

    (options, args) = parser.parse_args()

    options.bits = parse_bits(options.bits)

    inbound_runner = None
    if options.app in ("firefox", "fennec", "b2g"):
        inbound_runner = InboundRunner(appname=options.app,
                                       addons=options.addons,
                                       repo_name=options.repo_name,
                                       profile=options.profile,
                                       cmdargs=options.cmdargs,
                                       bits=options.bits,
                                       persist=options.persist)

    if options.inbound:
        if not options.last_good_revision or not options.first_bad_revision:
            print "If bisecting inbound, both --good-rev and --bad-rev " \
                " must be set"
            sys.exit(1)
        bisector = Bisector(None, inbound_runner, appname=options.app,
                            last_good_revision=options.last_good_revision,
                            first_bad_revision=options.first_bad_revision)
        bisector.bisect_inbound()
    else:
        if not options.good_date:
            options.good_date = "2009-01-01"
            print "No 'good' date specified, using " + options.good_date
        nightly_runner = NightlyRunner(appname=options.app, addons=options.addons,
                                       repo_name=options.repo_name,
                                       profile=options.profile,
                                       cmdargs=options.cmdargs,
                                       bits=options.bits,
                                       persist=options.persist)
        bisector = Bisector(nightly_runner, inbound_runner,
                            appname=options.app)
        bisector.bisect_nightlies(get_date(options.good_date),
                                  get_date(options.bad_date))


if __name__ == "__main__":
    cli()
