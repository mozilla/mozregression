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

#Call mozcommitbuilder
from mozcommitbuilder import builder

from runnightly import NightlyRunner
from utils import strsplit, get_date

class Bisector():
    def __init__(self, runner):
        self.runner = runner
        self.goodAppInfo = ''
        self.badAppInfo = ''
        self.currDate = ''

    def buildChangesets(self, goodDate, badDate):
      commitBuilder = builder.Builder()
      lastGoodChangeset = commitBuilder.changesetFromDay(str(goodDate))
      if(goodDate == badDate):
        firstBadChangeset = commitBuilder.getTip()
      else:
        firstBadChangeset = commitBuilder.changesetFromDay(str(badDate))


      print "\n Narrowed changeset range from " + lastGoodChangeset + " to " + firstBadChangeset +"\n"

      print "Time to do some bisecting and building!"
      commitBuilder.bisect(lastGoodChangeset, firstBadChangeset)


    def bisect(self, goodDate, badDate, appname="firefox"):
        midDate = goodDate + (badDate - goodDate) / 2
        if midDate == badDate or midDate == goodDate:
            print "\n\nLast good nightly: " + str(goodDate) + " First bad nightly: " + str(badDate) + "\n"
            print "Pushlog: " + self.getPushlogUrl(goodDate, badDate) + "\n"
            if appname == "firefox":
              print "Building changesets:"
              self.buildChangesets(goodDate, badDate)
            sys.exit()

        # run the nightly from that date
        dest = self.runner.start(midDate)
        while not dest:
            midDate += datetime.timedelta(days=1)
            if midDate == badDate:
                print "\n\nLast good nightly: " + str(goodDate) + " First bad nightly: " + str(badDate) + "\n"
                print "Pushlog: " + self.getPushlogUrl(goodDate, badDate) + "\n"
                if appname == "firefox":
                  print "Building changesets:"
                  self.buildChangesets(goodDate, badDate)
                sys.exit()
            dest = self.runner.start(midDate)

        self.prevDate = self.currDate
        self.currDate = midDate

        # wait for them to call it 'good' or 'bad'
        verdict = ""
        while verdict != 'good' and verdict != 'bad' and verdict != 'b' and verdict != 'g':
            verdict = raw_input("Was this nightly good or bad? (type 'good' or 'bad' and press Enter): ")

        self.runner.stop()
        if verdict == 'good' or verdict == 'g':
            self.goodAppInfo = self.runner.getAppInfo()
            self.bisect(midDate, badDate)
        else:
            self.badAppInfo = self.runner.getAppInfo()
            self.bisect(goodDate, midDate)

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
    parser.add_option("-n", "--app", dest="app", help="application name (firefox, mobile or thunderbird)",
                      metavar="[firefox|mobile|thunderbird]", default="firefox")
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
    bisector = Bisector(runner)
    bisector.bisect(get_date(options.good_date), get_date(options.bad_date), options.app)


if __name__ == "__main__":
    cli()
