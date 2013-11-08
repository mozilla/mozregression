#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import mozinfo
import sys
from optparse import OptionParser
from runnightly import NightlyRunner, parseBits
from utils import strsplit, get_date

class Bisector(object):
    def __init__(self, runner, appname="firefox"):
        self.runner = runner
        self.appname = appname
        self.goodAppInfo = ''
        self.badAppInfo = ''
        self.currDate = ''

    def findRegressionChset(self, goodDate, badDate):
        #Uses mozcommitbuilder to bisect on changesets
        #Only needed if they want to bisect, so we'll put the dependency here.
        from mozcommitbuilder import builder
        commitBuilder = builder.Builder()

        #One of these won't be set, so we need to download one more nightly and set it
        if self.goodAppInfo:
            lastGoodChangeset = self.goodAppInfo[1]
        else:
            #Download and get the info
            missingNightly = NightlyRunner()
            missingNightly.install(goodDate)
            lastGoodChangeset = missingNightly.getAppInfo()[1]

        if self.badAppInfo:
            firstBadChangeset = self.badAppInfo[1]
        else:
            #Download and get the info
            missingNightly = NightlyRunner()
            missingNightly.install(badDate)
            firstBadChangeset = missingNightly.getAppInfo()[1]

        print "\n Narrowed changeset range from " + lastGoodChangeset + " to " + firstBadChangeset +"\n"

        print "Time to do some bisecting and building!"
        commitBuilder.bisect(lastGoodChangeset, firstBadChangeset)
        quit()

    def build(self, goodDate, badDate):
        if self.appname == "firefox":
            print "Building changesets:"
            self.findRegressionChset(goodDate, badDate)
        else:
            print "Bisection on anything other than firefox is not currently supported."

    def printRange(self, goodDate, badDate):
        print "\n\nLast good nightly: " + str(goodDate) + "\nFirst bad nightly: " + str(badDate) + "\n"
        print "Pushlog:\n" + self.getPushlogUrl(goodDate, badDate) + "\n"
        verdict = raw_input("do you want to bisect further by fetching the repository and building? (y or n) ")
        if verdict == "y":
            self.build(goodDate, badDate)
        sys.exit()

    def bisect(self, goodDate, badDate, skips=0):
        midDate = goodDate + (badDate - goodDate) / 2
        
        midDate += datetime.timedelta(days=skips)

        if midDate == badDate or midDate == goodDate:
            self.printRange(goodDate, badDate)

        # run the nightly from that date
        dest = self.runner.start(midDate)
        while not dest:
            midDate += datetime.timedelta(days=1)
            if midDate == badDate:
                self.printRange(goodDate, badDate)
            dest = self.runner.start(midDate)

        self.prevDate = self.currDate
        self.currDate = midDate

        # wait for them to call it 'good' or 'bad'
        verdict = ""
        options = ['good','g','bad','b','skip','s','retry','r', 'exit']
        while verdict not in options:
            verdict = raw_input("Was this nightly good, bad, or broken? (type 'good', 'bad', 'skip', 'retry', or 'exit' and press Enter): ")

        self.runner.stop()
        if verdict == 'good' or verdict == 'g':
            self.goodAppInfo = self.runner.getAppInfo()
            self.bisect(midDate, badDate)
        elif verdict == 'bad' or verdict == 'b':
            self.badAppInfo = self.runner.getAppInfo()
            self.bisect(goodDate, midDate)
        elif verdict == 'skip' or verdict == 's':
            #skip -- go 1 day further down
            self.bisect(goodDate, badDate, skips=skips+1)
        elif verdict == 'exit':
            self.runner.stop()
            goodDateString = '%04d-%02d-%02d' % (goodDate.year, goodDate.month, goodDate.day)
            badDateString = '%04d-%02d-%02d' % (badDate.year, badDate.month, badDate.day)
            print 'Newest known good nightly: %s' % goodDateString
            print 'Oldest known bad nightly: %s' % badDateString
            print 'To resume, run:'
            print 'mozregression --good=%s --bad=%s' % (goodDateString, badDateString)
            return
        else:
            #retry -- since we're just calling ourselves with the same parameters, it does the same thing again
            self.bisect(goodDate, badDate)

    def getPushlogUrl(self, goodDate, badDate):
        # pushlogs are typically done with the oldest date first
        if goodDate < badDate:
            start = goodDate
            end = badDate
        else:
            start = badDate
            end = goodDate

        if not self.goodAppInfo or not self.badAppInfo:
            if self.goodAppInfo:
                (repo, chset) = self.goodAppInfo
            elif self.badAppInfo:
                (repo, chset) = self.badAppInfo
            else:
                repo = 'http://hg.mozilla.org/mozilla-central'
            return repo + "/pushloghtml?startdate=" + str(start) + "&enddate=" + str(end)

        (repo, good_chset) = self.goodAppInfo
        (repo, bad_chset) = self.badAppInfo
        return repo + "/pushloghtml?fromchange=" + good_chset + "&tochange=" + bad_chset

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
    (options, args) = parser.parse_args()

    options.bits = parseBits(options.bits)

    addons = strsplit(options.addons, ",")
    cmdargs = strsplit(options.cmdargs, ",")

    if not options.good_date:
        options.good_date = "2009-01-01"
        print "No 'good' date specified, using " + options.good_date

    runner = NightlyRunner(appname=options.app, addons=addons, repo_name=options.repo_name,
                           profile=options.profile, cmdargs=cmdargs, bits=options.bits,
                           persist=options.persist)
    bisector = Bisector(runner, appname=options.app)
    bisector.bisect(get_date(options.good_date), get_date(options.bad_date))


if __name__ == "__main__":
    cli()
