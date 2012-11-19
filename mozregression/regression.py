#!/usr/bin/env python
# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Mozilla Corporation Code.
#
# The Initial Developer of the Original Code is
# Heather Arthur
# Portions created by the Initial Developer are Copyright (C) 2009
# the Initial Developer. All Rights Reserved.
#
# Contributor(s): Heather Arthur <fayearthur@gmail.com>
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

import datetime
import sys
import subprocess
from optparse import OptionParser


from runnightly import NightlyRunner
from utils import strsplit, get_date, increment_day

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
        if not self.goodAppInfo or not self.badAppInfo:
            if self.goodAppInfo:
                (repo, chset) = self.goodAppInfo
            elif self.badAppInfo:
                (repo, chset) = self.badAppInfo
            else:
                repo = 'http://hg.mozilla.org/mozilla-central'
            return repo + "/pushloghtml?startdate=" + str(goodDate) + "&enddate=" + str(badDate)

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
    (options, args) = parser.parse_args()

    addons = strsplit(options.addons, ",")
    cmdargs = strsplit(options.cmdargs, ",")

    if not options.good_date:
        options.good_date = "2009-01-01"
        print "No 'good' date specified, using " + options.good_date

    runner = NightlyRunner(appname=options.app, addons=addons, repo_name=options.repo_name,
                           profile=options.profile, cmdargs=cmdargs)
    bisector = Bisector(runner, appname=options.app)
    bisector.bisect(get_date(options.good_date), get_date(options.bad_date))


if __name__ == "__main__":
    cli()
