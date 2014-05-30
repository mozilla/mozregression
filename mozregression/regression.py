#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import mozinfo
import sys
from optparse import OptionParser

from mozregression.utils import strsplit, get_date
from mozregression.inboundfinder import getInboundRevisions
from mozregression.runnightly import NightlyRunner, parseBits
from mozregression.runinbound import InboundRunner


class Bisector(object):

    currDate = ''
    foundRepo = None

    def __init__(self, nightly_runner, inbound_runner, appname="firefox",
                 lastGoodRevision=None, firstBadRevision=None):
        self.nightlyRunner = nightly_runner
        self.inboundRunner = inbound_runner
        self.appname = appname
        self.lastGoodRevision = lastGoodRevision
        self.firstBadRevision = firstBadRevision

    def findRegressionChset(self, last_good_revision, first_bad_revision):
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
            self.findRegressionChset(last_good_revision, first_bad_revision)
        else:
            print "Bisection on anything other than firefox is not" \
                  " currently supported."
            sys.exit()

    def printRange(self, goodDate=None, badDate=None):
        def _print_date_revision(name, revision, date):
            if date and revision:
                print "%s revision: %s (%s)" % (name, revision, date)
            elif revision:
                print "%s revision: %s" % (name, revision)
            elif date:
                print "%s build: %s" % (name, date)
        _print_date_revision("Last good", self.lastGoodRevision, goodDate)
        _print_date_revision("First bad", self.firstBadRevision, badDate)

        print "Pushlog:\n" + self.getPushlogUrl(goodDate, badDate) + "\n"

    def _ensureMetadata(self, good_date, bad_date):
        print "Ensuring we have enough metadata to get a pushlog..."
        if not self.lastGoodRevision:
            self.nightlyRunner.install(good_date)
            (self.foundRepo, self.lastGoodRevision) = \
                self.nightlyRunner.getAppInfo()
        if not self.firstBadRevision:
            self.nightlyRunner.install(bad_date)
            (self.foundRepo, self.firstBadRevision) = \
                self.nightlyRunner.getAppInfo()

    def _get_verdict(self, build_type, offerSkip=True):
        verdict = ""
        options = ['good', 'g', 'bad', 'b', 'retry', 'r']
        if offerSkip:
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

    def bisect_inbound(self, inboundRevisions=None):
        if not inboundRevisions:
            print "Getting inbound builds between %s and %s" % (
                self.lastGoodRevision, self.firstBadRevision)
            inboundRevisions = getInboundRevisions(
                self.lastGoodRevision, self.firstBadRevision,
                appName=self.inboundRunner.appName,
                bits=self.inboundRunner.bits)

            if not inboundRevisions:
                print "Oh noes, no (more) inbound revisions :("
                self.offer_build(self.lastGoodRevision,
                                 self.firstBadRevision)
                return
        # hardcode repo to mozilla-central (if we use inbound, we may be
        # missing some revisions that went into the nightlies which we may
        # also be comparing against...)

        mid = len(inboundRevisions) / 2
        print "Testing inbound build with timestamp %s," \
              " revision %s" % (inboundRevisions[mid][1],
                                inboundRevisions[mid][0])
        self.inboundRunner.start(inboundRevisions[mid][1])

        verdict = self._get_verdict('inbound', offerSkip=False)
        self.inboundRunner.stop()
        self.foundRepo = self.inboundRunner.getAppInfo()[0]
        if verdict == 'g':
            self.lastGoodRevision = self.inboundRunner.getAppInfo()[1]
        elif verdict == 'b':
            self.firstBadRevision = self.inboundRunner.getAppInfo()[1]
        elif verdict == 'r':
            # do the same thing over again
            self.bisect_inbound(inboundRevisions=inboundRevisions)
            return
        elif verdict == 'e':
            print 'Newest known good inbound revision: %s' \
                % self.lastGoodRevision
            print 'Oldest known bad inbound revision: %s' \
                % self.firstBadRevision

            print 'To resume, run:'
            self.inboundRunner.printResumeInfo(self.lastGoodRevision,
                                               self.firstBadRevision)
            return

        if len(inboundRevisions) > 1 and verdict == 'g':
            self.bisect_inbound(inboundRevisions[(mid+1):])
        elif len(inboundRevisions) > 1 and verdict == 'b':
            self.bisect_inbound(inboundRevisions[:mid])
        else:
            # no more inbounds to be bisect, we must build
            print "No more inbounds to bisect"
            self.printRange()
            self.offer_build(self.lastGoodRevision, self.firstBadRevision)

    def bisect_nightlies(self, good_date, bad_date, skips=0):
        mid_date = good_date + (bad_date - good_date) / 2

        mid_date += datetime.timedelta(days=skips)

        if mid_date == bad_date or mid_date == good_date:
            print "Got as far as we can go bisecting nightlies..."
            if self.appname == 'firefox' or self.appname == 'fennec':
                self._ensureMetadata(good_date, bad_date)
                self.printRange(good_date, bad_date)
                print "... attempting to bisect inbound builds (starting " \
                    "from previous day, to make sure no inbound revision is " \
                    "missed)"
                prev_date = good_date - datetime.timedelta(days=1)
                self.nightlyRunner.install(prev_date)
                self.lastGoodRevision = self.nightlyRunner.getAppInfo()[1]
                self.bisect_inbound()
                return
            else:
                print "(no more options with %s)" % self.appname
                sys.exit()

        # run the nightly from that date
        print "Running nightly for %s" % mid_date
        dest = self.nightlyRunner.start(mid_date)
        while not dest:
            mid_date += datetime.timedelta(days=1)
            if mid_date == bad_date:
                self.printRange(good_date, bad_date)
            dest = self.nightlyRunner.start(mid_date)

        self.prevDate = self.currDate
        self.currDate = mid_date

        verdict = self._get_verdict('nightly')
        self.nightlyRunner.stop()
        self.foundRepo = self.nightlyRunner.getAppInfo()[0]
        if verdict == 'g':
            self.lastGoodRevision = self.nightlyRunner.getAppInfo()[1]
            self.bisect_nightlies(mid_date, bad_date)
        elif verdict == 'b':
            self.firstBadRevision = self.nightlyRunner.getAppInfo()[1]
            self.bisect_nightlies(good_date, mid_date)
        elif verdict == 's':
            # skip -- go 1 day further down
            self.bisect_nightlies(good_date, bad_date, skips=skips+1)
        elif verdict == 'e':
            self.nightlyRunner.stop()
            good_date_string = '%04d-%02d-%02d' % (good_date.year,
                                                   good_date.month,
                                                   good_date.day)
            bad_date_string = '%04d-%02d-%02d' % (bad_date.year,
                                                  bad_date.month,
                                                  bad_date.day)
            print 'Newest known good nightly: %s' % good_date_string
            print 'Oldest known bad nightly: %s' % bad_date_string
            print 'To resume, run:'
            self.nightlyRunner.printResumeInfo(good_date_string,
                                               bad_date_string)
            return
        else:
            # retry -- since we're just calling ourselves with the same
            # parameters, it does the same thing again
            self.bisect_nightlies(good_date, bad_date)

    def getPushlogUrl(self, good_date, bad_date):
        # if we don't have precise revisions, we need to resort to just
        # using handwavey dates
        if not self.lastGoodRevision or not self.firstBadRevision:
            # pushlogs are typically done with the oldest date first
            if good_date < bad_date:
                start = good_date
                end = bad_date
            else:
                start = bad_date
                end = good_date
            return "%s/pushloghtml?startdate=%s&enddate=%s" % (self.foundRepo,
                                                               start, end)

        return "%s/pushloghtml?fromchange=%s&tochange=%s" % (
            self.foundRepo, self.lastGoodRevision, self.firstBadRevision)


def cli():
    parser = OptionParser()
    parser.add_option("-b", "--bad", dest="bad_date",
                      help="first known bad nightly build, default is today",
                      metavar="YYYY-MM-DD", default=str(datetime.date.today()))
    parser.add_option("-g", "--good", dest="good_date",
                      help="last known good nightly build",
                      metavar="YYYY-MM-DD", default=None)
    parser.add_option("-e", "--addons", dest="addons",
                      help="list of addons to install", metavar="PATH1,PATH2",
                      default="")
    parser.add_option("-p", "--profile", dest="profile",
                      help="profile to use with nightlies", metavar="PATH")
    parser.add_option("-a", "--args", dest="cmdargs",
                      help="command-line arguments to pass to the application",
                      metavar="ARG1,ARG2", default="")
    parser.add_option("-n", "--app", dest="app",
                      help="application name  (firefox, fennec or"
                      " thunderbird)",
                      metavar="[firefox|fennec|thunderbird]",
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

    options.bits = parseBits(options.bits)

    addons = strsplit(options.addons, ",")
    cmdargs = strsplit(options.cmdargs, ",")

    inbound_runner = None
    if options.app == "firefox" or options.app == "fennec":
        inbound_runner = InboundRunner(appname=options.app,
                                       addons=addons,
                                       repo_name=options.repo_name,
                                       profile=options.profile,
                                       cmdargs=cmdargs, bits=options.bits,
                                       persist=options.persist)

    if options.inbound:
        if not options.last_good_revision or not options.first_bad_revision:
            print "If bisecting inbound, both --good-rev and --bad-rev " \
                " must be set"
            sys.exit(1)
        bisector = Bisector(None, inbound_runner, appname=options.app,
                            lastGoodRevision=options.last_good_revision,
                            firstBadRevision=options.first_bad_revision)
        bisector.bisect_inbound()
    else:
        if not options.good_date:
            options.good_date = "2009-01-01"
            print "No 'good' date specified, using " + options.good_date
        nightly_runner = NightlyRunner(appname=options.app, addons=addons,
                                       repo_name=options.repo_name,
                                       profile=options.profile,
                                       cmdargs=cmdargs,
                                       bits=options.bits,
                                       persist=options.persist)
        bisector = Bisector(nightly_runner, inbound_runner,
                            appname=options.app)
        bisector.bisect_nightlies(get_date(options.good_date),
                                  get_date(options.bad_date))


if __name__ == "__main__":
    cli()
