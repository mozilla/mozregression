#!/usr/bin/env python
import datetime
import sys
from optparse import OptionParser
from runnightly import NightlyRunner
from runnightly import get_date
from runnightly import strsplit, get_date

class Bisector():
    def __init__(self, runner): 
        self.runner = runner
        self.currAppInfo = ''
        self.currDate = ''

    def bisect(self, goodDate, badDate):
        midDate = goodDate + (badDate - goodDate) / 2
        if midDate == badDate or midDate == goodDate:
            print "\n\nLast good nightly: " + str(goodDate) + " First bad nightly: " + str(badDate) + "\n"
            print "Pushlog: " + self.getPushlogUrl(goodDate, badDate) + "\n"
            sys.exit()
    
        # run the nightly from that date
        dest = self.runner.start(midDate)
        while not dest:
            print "\nCould not find nightly for " + str(midDate)
            midDate += datetime.timedelta(days=1)
            if midDate == badDate:
                print "\n\nLast good nightly: " + str(goodDate) + " First bad nightly: " + str(badDate) + "\n"
                print "Pushlog: " + self.getPushlogUrl(goodDate, badDate) + "\n"
                sys.exit()
            dest = self.runner.start(midDate)
        
        self.prevAppInfo = self.currAppInfo
        self.prevDate = self.currDate
        self.currAppInfo = self.runner.getAppInfo()
        self.currDate = midDate

        # wait for them to call it 'good' or 'bad'
        verdict = ""
        while verdict != 'good' and verdict != 'bad' and verdict != 'b' and verdict != 'g':
            verdict = raw_input("Was this nightly good or bad? (type 'good' or 'bad' and press Enter): ")

        self.runner.stop()
        if verdict == 'good' or verdict == 'g':
            self.bisect(midDate, badDate)
        else:
            self.bisect(goodDate, midDate)

    def getPushlogUrl(self, goodDate, badDate):
        if not self.currAppInfo or not self.prevAppInfo:
            if self.currAppInfo:
                (repo, chset) = self.currAppInfo
            elif self.prevAppInfo:
                (repo, chset) = self.prevAppInfo
            else:
                repo = ''

            return repo + "/pushloghtml?startdate=" + str(goodDate) + "&enddate=" + str(badDate)

        (repo, chset1) = self.currAppInfo
        (repo, chset2) = self.prevAppInfo
        if self.currDate > self.prevDate:
            return repo + "/pushloghtml?fromchange=" + chset2 + "&tochange=" + chset1
        return repo + "/pushloghtml?fromchange=" + chset1 + "&tochange=" + chset2
        
def cli():
    parser = OptionParser()
    parser.add_option("-b", "--bad", dest="badDate",help="first known bad nightly build, default is today",metavar="YYYY-MM-DD", default=str(datetime.date.today()))
    parser.add_option("-g", "--good", dest="goodDate",help="last known good nightly build", metavar="YYYY-MM-DD")
    parser.add_option("-e", "--addons", dest="addons",help="list of addons to install", metavar="PATH1,PATH2", default="")
    parser.add_option("-p", "--profile", dest="profile", help="profile to use with nightlies", metavar="PATH")
    parser.add_option("-a", "--args", dest="cmdargs", help="command-line arguments to pass to the application", metavar="ARG1,ARG2", default="")
    (options, args) = parser.parse_args()

    addons = strsplit(options.addons, ",")
    cmdargs = strsplit(options.cmdargs, ",")

    runner = NightlyRunner(addons=addons, profile=options.profile, cmdargs=cmdargs)
    bisector = Bisector(runner)
    bisector.bisect(get_date(options.goodDate), get_date(options.badDate))


if __name__ == "__main__":
    cli()
