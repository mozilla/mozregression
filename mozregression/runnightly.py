#!/usr/bin/env python
import os
import datetime
import httplib2
import re
import sys
import platform
import subprocess
from optparse import OptionParser
from BeautifulSoup import BeautifulSoup

from mozrunner import FirefoxProfile
from mozrunner import Runner
from mozInstall import MozInstaller
from mozInstall import rmdirRecursive
from utils import strsplit, download_url, get_date

def currentPlatform():
    (bits, linkage) = platform.architecture()

    os = platform.system()
    if os == 'Microsoft' or os == 'Windows' or re.match(".*cygwin.*", os):
        return "Windows " + bits # 'Windows 32bit'
    elif os == 'Linux':
        return "Linux " + bits
    elif os == 'Darwin' or os == 'Mac':
        return "Mac " + bits        

class Nightly(object):
    def download(self, date=datetime.date.today(), dest=None):
        url = self.getBuildUrl(date)
        if url:
            if not dest:
                dest = os.path.basename(url)
            print "\nDownloading nightly...\n"  #TODO: doesn't belong here
            download_url(url, dest)
            self.dest = dest
            return True
        else:
            return False

    def install(self):
        rmdirRecursive("app")
        subprocess._cleanup = lambda : None # mikeal's fix for subprocess threading bug
        MozInstaller(src=self.dest, dest="app")
    

class FirefoxNightly(Nightly):
    def __init__(self, platform=currentPlatform()):
        self.profileClass = FirefoxProfile

        if platform == "Windows 64bit":
            print "No nightly builds available for 64 bit Windows"
            sys.exit()
        if platform == "Windows" or platform == "Windows 32bit":
            self.buildRegex = ".*win32.zip"
            self.processName = "firefox.exe"
            self.executablePath = "app/firefox/firefox.exe"
        elif platform == "Linux" or platform == "Linux 32bit":
            self.buildRegex = ".*linux-i686.tar.bz2"
            self.processName = "firefox-bin"
            self.executablePath = "app/firefox/firefox"
        elif platform == "Linux 64bit":
            self.buildRegex = ".*linux-x86_64.tar.bz2"
            self.processName = "firefox-bin"
            self.executablePath = "app/firefox/firefox"
        elif platform == "Mac" or platform=="Mac 32bit" or platform == "Mac 64bit":
            self.buildRegex = ".*mac.dmg"
            self.processName = "firefox-bin"
            self.executablePath = "app/Minefield.app/Contents/MacOS/firefox-bin"

    def getBuildUrl(self, date):
        # we don't know which hour the build was made, so look through all of them
        for i in [3, 2, 4, 5, 6, 1, 0] + range(7, 23):
            url = self.getUrl(date, i)
            if url:
                return url
                
    def formatDatePart(self, part):
        if part < 10:
            part = "0" + str(part)
        return str(part)

    def getUrl(self, date, hour):
        url = "http://ftp.mozilla.org/pub/mozilla.org/firefox/nightly/"
        year = str(date.year)
        month = self.formatDatePart(date.month)
        day = self.formatDatePart(date.day)
        url += year + "/" + month + "/" + year + "-" + month + "-" + day + "-"
        url += self.formatDatePart(hour) + "-" + self.getFirefoxTrunk(date) + "/"

        # now parse the page for the correct build url
        h = httplib2.Http();
        resp, content = h.request(url, "GET")
        if resp.status != 200:
            return False
        soup = BeautifulSoup(content)
        for link in soup.findAll('a'):
            href = link.get("href")
            if re.match(self.buildRegex, href):     
                return url + href

    def getFirefoxTrunk(self, date):
        if date < datetime.date(2008, 06, 17):
            return "trunk"
        else:
            return "mozilla-central"

    def getAppInfo(self):
        appIni = open(os.path.join(os.path.dirname(self.executablePath), "application.ini"), 'r')
        appInfo = appIni.read()
        appIni.close()
        repo = re.search('^SourceRepository\=(.+)', appInfo, re.M).group(1)
        changeset = re.search('^SourceStamp\=(.+)', appInfo, re.M).group(1)
        return (repo, changeset)


class NightlyRunner(object):
    def __init__(self, addons=None, application=FirefoxNightly(currentPlatform()), profile=None, cmdargs=[]):
        self.addons = addons
        self.profile = profile
        self.application = application
        self.cmdargs = cmdargs

    def start(self, date=datetime.date.today()):
        if not self.application.download(date=date):
            return False # download failed
        self.application.install()

        if self.profile:
            profile = self.application.profileClass(profile=self.profile, create_new=False, addons=self.addons)
        elif len(self.addons):
            profile = self.application.profileClass(addons=self.addons)
        else:
            profile = self.application.profileClass()

        print "running Firefox nightly from " + str(date) + "\n"
        self.runner = Runner(binary=self.application.executablePath, cmdargs=self.cmdargs, profile=profile)
        self.runner.names = [self.application.processName]
        self.runner.start()
        return True

    def stop(self):
        self.runner.stop()

    def getAppInfo(self):
        return self.application.getAppInfo()
        
def cli():
    parser = OptionParser()
    parser.add_option("-d", "--date", dest="date", help="date of the nightly", metavar="YYYY-MM-DD", default=str(datetime.date.today()))
    parser.add_option("-a", "--addons", dest="addons", help="list of addons to install", metavar="PATH1,PATH2", default="")
    parser.add_option("-p", "--profile", dest="profile", help="path to profile to user", metavar="PATH")
    (options, args) = parser.parse_args()

    runner = NightlyRunner(addons=strsplit(options.addons, ","), profile=options.profile)
    runner.start(get_date(options.date))


if __name__ == "__main__":
    cli()
