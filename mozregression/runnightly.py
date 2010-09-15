#!/usr/bin/env python
import os
import datetime
import httplib2
import re
import sys
import platform
import subprocess
from optparse import OptionParser
from ConfigParser import ConfigParser
from BeautifulSoup import BeautifulSoup

try:
  from mozprofile import FirefoxProfile
  from mozprofile import ThunderbirdProfile
except:
  from mozrunner import FirefoxProfile
  from mozrunner import ThunderbirdProfile

from mozrunner import Runner
from mozInstall import MozInstaller
from mozInstall import rmdirRecursive
from utils import strsplit, download_url, get_date, get_platform 

class Nightly(object):
    def __init__(self):
        platform=get_platform()
        if platform['name'] == "Windows":
            if platform['bits'] == '64bit':
                print "No nightly builds available for 64 bit Windows"
                sys.exit()
            self.buildRegex = ".*win32.zip"
            self.processName = self.name + ".exe"
            self.binary = "moznightlyapp/" + self.name + "/" + self.name + ".exe"
        elif platform['name'] == "Linux":
            self.processName = self.name + "-bin"
            self.binary = "moznightlyapp/" + self.name + "/" + self.name
            if platform['bits'] == '64bit':
                self.buildRegex = ".*linux-x86_64.tar.bz2"
            else:
                self.buildRegex = ".*linux-i686.tar.bz2"
        elif platform['name'] == "Mac":
            self.buildRegex = ".*mac.dmg"
            self.processName = self.name + "-bin"
            self.binary = "moznightlyapp/" + self.nickname + ".app/Contents/MacOS/" + self.name + "-bin"

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
        rmdirRecursive("moznightlyapp")
        subprocess._cleanup = lambda : None # mikeal's fix for subprocess threading bug
        MozInstaller(src=self.dest, dest="moznightlyapp") 
    
    def getBuildUrl(self, date):
        # we don't know which hour the build was made, so look through all of them
        for i in [3, 2, 4, 5, 6, 1, 0] + range(7, 23):
            url = self.getUrl(date, i)
            if url:
                return url

    def getUrl(self, date, hour):
        url = "http://ftp.mozilla.org/pub/mozilla.org/" + self.name + "/nightly/"
        year = str(date.year)
        month = self.formatDatePart(date.month)
        day = self.formatDatePart(date.day)
        url += year + "/" + month + "/" + year + "-" + month + "-" + day + "-"
        url += self.formatDatePart(hour) + "-" + self.getTrunkName(date) + "/"

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
                
    def formatDatePart(self, part):
        if part < 10:
            part = "0" + str(part)
        return str(part)
        
    def getAppInfo(self):
        parser = ConfigParser()
        ini_file = os.path.join(os.path.dirname(self.binary), "application.ini")
        parser.read(ini_file)
        changeset = parser.get('App', 'SourceStamp')
        repo = parser.get('App', 'SourceRepository')
        return (repo, changeset)
        
class ThunderbirdNightly(Nightly):

    name = 'thunderbird' 
    nickname = 'Shredder'
    profileClass = ThunderbirdProfile
                
    def getTrunkName(self, date):
        # sneaking this in here
        if get_platform()['name'] == "Windows" and date < datetime.date(2010, 03, 18):
           # no .zip package for Windows, can't use the installer
           print "Can't run Windows builds before 2010-03-18"
           sys.exit()
      
        if date < datetime.date(2008, 07, 26):
            return "trunk"
        elif date < datetime.date(2009, 1, 9):
            return "comm-central"
        elif date < datetime.date(2010, 8, 21):
            return "comm-central-trunk"
        else:
            return "comm-central"


class FirefoxNightly(Nightly):
    name = 'firefox'
    nickname = 'Minefield'
    profileClass = FirefoxProfile

    def getTrunkName(self, date):
        if date < datetime.date(2008, 06, 17):
            return "trunk"
        else:
            return "mozilla-central"


class NightlyRunner(object):
    def __init__(self, addons=None, appname="firefox", profile=None, cmdargs=[]):
        if appname.lower() == 'thunderbird':
           self.app = ThunderbirdNightly()
        else:
           self.app = FirefoxNightly()
        self.addons = addons
        self.profile = profile
        self.cmdargs = cmdargs

    def start(self, date=datetime.date.today()):
        if not self.app.download(date=date):
            print "could not find nightly from " + str(date)
            return False # download failed
        self.app.install()

        if self.profile:
            profile = self.app.profileClass(profile=self.profile, addons=self.addons)
        elif len(self.addons):
            profile = self.app.profileClass(addons=self.addons)
        else:
            profile = self.app.profileClass()

        print "running nightly from " + str(date) + "\n"
        self.runner = Runner(binary=self.app.binary, cmdargs=self.cmdargs, profile=profile)
        self.runner.names = [self.app.processName]
        self.runner.start()
        return True

    def stop(self):
        self.runner.stop()

    def getAppInfo(self):
        return self.app.getAppInfo()
        
def cli():
    parser = OptionParser()
    parser.add_option("-d", "--date", dest="date", help="date of the nightly",
                      metavar="YYYY-MM-DD", default=str(datetime.date.today()))
    parser.add_option("-a", "--addons", dest="addons", help="list of addons to install",
                      metavar="PATH1,PATH2", default="")
    parser.add_option("-p", "--profile", dest="profile", help="path to profile to user", metavar="PATH")
    parser.add_option("-n", "--app", dest="app", help="application name (firefox or thunderbird)",
                      metavar="[firefox|thunderbird]", default="firefox")
    (options, args) = parser.parse_args()

    runner = NightlyRunner(appname=options.app, addons=strsplit(options.addons, ","), profile=options.profile)
    runner.start(get_date(options.date))


if __name__ == "__main__":
    cli()
