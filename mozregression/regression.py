#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import mozinfo
import sys
from optparse import OptionParser
from inboundfinder import getInboundRevisions
from runnightly import NightlyRunner, parseBits
from runinbound import InboundRunner
from utils import strsplit, get_date

class Bisector(object):

    currDate = ''
    foundRepo = None

    def __init__(self, nightlyRunner, inboundRunner, appname="firefox",
                 lastGoodRevision=None, firstBadRevision=None):
        self.nightlyRunner = nightlyRunner
        self.inboundRunner = inboundRunner
        self.appname = appname
        self.lastGoodRevision = lastGoodRevision
        self.firstBadRevision = firstBadRevision

    def findRegressionChset(self, lastGoodRevision, firstBadRevision):
        #Uses mozcommitbuilder to bisect on changesets
        #Only needed if they want to bisect, so we'll put the dependency here.
        from mozcommitbuilder import builder
        commitBuilder = builder.Builder()

        print "\n Narrowed changeset range from " + lastGoodRevision + " to " + firstBadRevision +"\n"

        print "Time to do some bisecting and building!"
        commitBuilder.bisect(lastGoodRevision, firstBadRevision)
        quit()

    def offer_build(self, lastGoodRevision, firstBadRevision):
        verdict = raw_input("do you want to bisect further by fetching the repository and building? (y or n) ")
        if verdict != "y":
            sys.exit()

        if self.appname == "firefox":
            self.findRegressionChset(lastGoodRevision, firstBadRevision)
        else:
            print "Bisection on anything other than firefox is not currently supported."
            sys.exit()

    def printRange(self, goodDate=None, badDate=None):
        def _printDateRevision(name, revision, date):
            if date and revision:
                print "%s revision: %s (%s)" % (name, revision, date)
            elif revision:
                print "%s revision: %s" % (name, revision)
            elif date:
                print "%s build: %s" % (name, date)
        _printDateRevision("Last good", self.lastGoodRevision, goodDate)
        _printDateRevision("First bad", self.firstBadRevision, badDate)

        print "Pushlog:\n" + self.getPushlogUrl(goodDate, badDate) + "\n"

    def _ensureMetadata(self, goodDate, badDate):
        print "Ensuring we have enough metadata to get a pushlog..."
        if not self.lastGoodRevision:
            self.nightlyRunner.install(goodDate)
            (self.foundRepo, self.lastGoodRevision) = \
                self.nightlyRunner.getAppInfo()
        if not self.firstBadRevision:
            self.nightlyRunner.install(badDate)
            (self.foundRepo, self.firstBadRevision) = \
                self.nightlyRunner.getAppInfo()

    def _get_verdict(self, buildType, offerSkip=True):
        verdict = ""
        options = ['good','g','bad','b','retry','r']
        if offerSkip:
            options += ['skip','s']
        options += ['exit']
        while verdict not in options:
            verdict = raw_input("Was this %s build good, bad, or broken? (type 'good', 'bad', 'skip', 'retry', or 'exit' and press Enter): " % buildType)

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
        print "Testing inbound build with timestamp %s, revision %s" % (inboundRevisions[mid][1],
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
            print 'Newest known good inbound revision: %s' % self.lastGoodRevision
            print 'Oldest known bad inbound revision: %s' % self.firstBadRevision
            print 'To resume, run:'
            print 'mozregression --inbound --good-rev=%s --bad-rev=%s' % (
                self.lastGoodRevision, self.firstBadRevision)
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

    def bisect_nightlies(self, goodDate, badDate, skips=0):
        midDate = goodDate + (badDate - goodDate) / 2

        midDate += datetime.timedelta(days=skips)

        if midDate == badDate or midDate == goodDate:
            print "Got as far as we can go bisecting nightlies..."
            self._ensureMetadata(goodDate, badDate)
            if self.appname == 'firefox' or self.appname == 'fennec':
                self.printRange(goodDate, badDate)
                print "... attempting to bisect inbound builds"
                self.bisect_inbound()
                return
            else:
                print "(no more options with %s)" % self.appname
                sys.exit()

        # run the nightly from that date
        print midDate
        dest = self.nightlyRunner.start(midDate)
        while not dest:
            midDate += datetime.timedelta(days=1)
            if midDate == badDate:
                self.printRange(goodDate, badDate)
            dest = self.nightlyRunner.start(midDate)

        self.prevDate = self.currDate
        self.currDate = midDate

        verdict = self._get_verdict('nightly')
        self.nightlyRunner.stop()
        self.foundRepo = self.nightlyRunner.getAppInfo()[0]
        if verdict == 'g':
            self.lastGoodRevision = self.nightlyRunner.getAppInfo()[1]
            self.bisect_nightlies(midDate, badDate)
        elif verdict == 'b':
            self.firstBadRevision = self.nightlyRunner.getAppInfo()[1]
            self.bisect_nightlies(goodDate, midDate)
        elif verdict == 's':
            #skip -- go 1 day further down
            self.bisect_nightlies(goodDate, badDate, skips=skips+1)
        elif verdict == 'e':
            self.nightlyRunner.stop()
            goodDateString = '%04d-%02d-%02d' % (goodDate.year, goodDate.month, goodDate.day)
            badDateString = '%04d-%02d-%02d' % (badDate.year, badDate.month, badDate.day)
            print 'Newest known good nightly: %s' % goodDateString
            print 'Oldest known bad nightly: %s' % badDateString
            print 'To resume, run:'
            print 'mozregression --good=%s --bad=%s' % (goodDateString, badDateString)
            return
        else:
            #retry -- since we're just calling ourselves with the same parameters, it does the same thing again
            self.bisect_nightlies(goodDate, badDate)

    def getPushlogUrl(self, goodDate, badDate):
        # if we don't have precise revisions, we need to resort to just
        # using handwavey dates
        if not self.lastGoodRevision or not self.firstBadRevision:
            # pushlogs are typically done with the oldest date first
            if goodDate < badDate:
                start = goodDate
                end = badDate
            else:
                start = badDate
                end = goodDate
            return "%s/pushloghtml?startdate=%s&enddate=%s" % (self.foundRepo,
                                                               start, end)

        return "%s/pushloghtml?fromchange=%s&tochange=%s" % (
            self.foundRepo, self.lastGoodRevision, self.firstBadRevision)

def cli():
    parser = OptionParser()
    parser.add_option("-b", "--bad", dest="bad_date",help="first known bad nightly build, default is today",
                      metavar="YYYY-MM-DD", default=str(datetime.date.today()))
    parser.add_option("-g", "--good", dest="good_date",help="last known good nightly build",
                      metavar="YYYY-MM-DD", default=None)
    parser.add_option("-e", "--addons", dest="addons",help="list of addons to install", metavar="PATH1,PATH2", default="")
    parser.add_option("-p", "--profile", dest="profile", help="profile to use with nightlies", metavar="PATH")
    parser.add_option("-a", "--args", dest="cmdargs", help="command-line arguments to pass to the application",
                      metavar="ARG1,ARG2", default="")
    parser.add_option("-n", "--app", dest="app", help="application name (firefox, fennec or thunderbird)",
                      metavar="[firefox|fennec|thunderbird]", default="firefox")
    parser.add_option("-r", "--repo", dest="repo_name", help="repository name on ftp.mozilla.org",
                      metavar="[tracemonkey|mozilla-1.9.2]", default=None)
    parser.add_option("--bits", dest="bits", help="force 32 or 64 bit version (only applies to x86_64 boxes)",
                      choices=("32","64"), default=mozinfo.bits)
    parser.add_option("--persist", dest="persist", help="the directory in which files are to persist ie. /Users/someuser/Documents")
    parser.add_option("--inbound", action="store_true", dest="inbound", help="use inbound instead of nightlies (use --good-rev and --bad-rev options")
    parser.add_option("--bad-rev", dest="firstBadRevision",help="first known bad revision (use with --inbound)")
    parser.add_option("--good-rev", dest="lastGoodRevision",help="last known good revision (use with --inbound)")

    (options, args) = parser.parse_args()

    options.bits = parseBits(options.bits)

    addons = strsplit(options.addons, ",")
    cmdargs = strsplit(options.cmdargs, ",")

    inboundRunner = None
    if options.app == "firefox" or options.app == "fennec":
        inboundRunner = InboundRunner(appname=options.app,
                                      addons=addons,
                                      repo_name=options.repo_name,
                                      profile=options.profile,
                                      cmdargs=cmdargs, bits=options.bits,
                                      persist=options.persist)

    if options.inbound:
        if not options.lastGoodRevision or not options.firstBadRevision:
            print "If bisecting inbound, both --good-rev and --bad-rev " \
                " must be set"
            sys.exit(1)
        bisector = Bisector(None, inboundRunner, appname=options.app,
                            lastGoodRevision=options.lastGoodRevision,
                            firstBadRevision=options.firstBadRevision)
        bisector.bisect_inbound()
    else:
        if not options.good_date:
            options.good_date = "2009-01-01"
            print "No 'good' date specified, using " + options.good_date
        nightlyRunner = NightlyRunner(appname=options.app, addons=addons,
                                      repo_name=options.repo_name,
                                      profile=options.profile, cmdargs=cmdargs,
                                      bits=options.bits,
                                      persist=options.persist)
        bisector = Bisector(nightlyRunner, inboundRunner, appname=options.app)
        bisector.bisect_nightlies(get_date(options.good_date),
                                  get_date(options.bad_date))


if __name__ == "__main__":
    cli()
