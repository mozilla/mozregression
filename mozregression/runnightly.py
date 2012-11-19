#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import os
import httplib2
import platform
import re
import subprocess
import sys

from mozfile import rmtree
from mozprofile import FirefoxProfile
from mozprofile import ThunderbirdProfile
from mozrunner import Runner
from optparse import OptionParser
from ConfigParser import ConfigParser
from BeautifulSoup import BeautifulSoup

from mozInstall import MozInstaller
from utils import strsplit, download_url, get_date, get_platform

class Nightly(object):
    def __init__(self, repo_name=None):
        platform=get_platform()
        if platform['name'] == "Windows":
            if platform['bits'] == '64':
                print "No nightly builds available for 64 bit Windows"
                sys.exit()
            self.buildRegex = ".*win32.zip"
            self.processName = self.name + ".exe"
            self.binary = "moznightlyapp/" + self.name + "/" + self.name + ".exe"
        elif platform['name'] == "Linux":
            self.processName = self.name + "-bin"
            self.binary = "moznightlyapp/" + self.name + "/" + self.name
            if platform['bits'] == '64':
                self.buildRegex = ".*linux-x86_64.tar.bz2"
            else:
                self.buildRegex = ".*linux-i686.tar.bz2"
        elif platform['name'] == "Mac":
            self.buildRegex = ".*mac.*\.dmg"
            self.processName = self.name + "-bin"
            self.binary = "moznightlyapp/Mozilla.app/Contents/MacOS/" + self.name + "-bin"
        self.repo_name = repo_name
        self._monthlinks = {}
        self.lastdest = None

    def cleanup(self):
        rmtree('moznightlyapp')
        if self.lastdest:
            os.remove(self.lastdest)

    __del__ = cleanup

    def download(self, date=datetime.date.today(), dest=None):
        url = self.getBuildUrl(date)
        if url:
            if not dest:
                dest = os.path.basename(url)
            print "Downloading nightly from %s" % date
            if self.lastdest:
                os.remove(self.lastdest)
            download_url(url, dest)
            self.dest = self.lastdest = dest
            return True
        else:
            return False

    def install(self):
        rmtree("moznightlyapp")
        subprocess._cleanup = lambda : None # mikeal's fix for subprocess threading bug
        MozInstaller(src=self.dest, dest="moznightlyapp", dest_app="Mozilla.app")
        return True

    @staticmethod
    def urlLinks(url):
        res = [] # do not return a generator but an array, so we can store it for later use

        h = httplib2.Http();
        resp, content = h.request(url, "GET")
        if resp.status != 200:
            return res

        soup = BeautifulSoup(content)
        for link in soup.findAll('a'):
            res.append(link)
        return res

    def getBuildUrl(self, date):
        url = "http://ftp.mozilla.org/pub/mozilla.org/" + self.appName + "/nightly/"
        year = str(date.year)
        month = "%02d" % date.month
        day = "%02d" % date.day
        repo_name = self.repo_name or self.getRepoName(date)
        url += year + "/" + month + "/"

        linkRegex = '^' + year + '-' + month + '-' + day + '-' + '[\d-]+' + repo_name + '/$'
        cachekey = year + '-' + month
        if cachekey in self._monthlinks:
            monthlinks = self._monthlinks[cachekey]
        else:
            monthlinks = self.urlLinks(url)
            self._monthlinks[cachekey] = monthlinks

        # first parse monthly list to get correct directory
        for dirlink in monthlinks:
            dirhref = dirlink.get("href")
            if re.match(linkRegex, dirhref):
                # now parse the page for the correct build url
                for link in self.urlLinks(url + dirhref):
                    href = link.get("href")
                    if re.match(self.buildRegex, href):
                        return url + dirhref + href

        return False

    def getAppInfo(self):
        parser = ConfigParser()
        ini_file = os.path.join(os.path.dirname(self.binary), "application.ini")
        parser.read(ini_file)
        try:
            changeset = parser.get('App', 'SourceStamp')
            repo = parser.get('App', 'SourceRepository')
            return (repo, changeset)
        except:
            return ("", "")

    def start(self, profile, addons, cmdargs):
        if profile:
            profile = self.profileClass(profile=profile, addons=addons)
        elif len(addons):
            profile = self.profileClass(addons=addons)
        else:
            profile = self.profileClass()

        self.runner = Runner(binary=self.binary, cmdargs=cmdargs, profile=profile)
        self.runner.names = [self.processName]
        self.runner.start()
        return True

    def stop(self):
        self.runner.stop()

    def wait(self):
        self.runner.wait()

class ThunderbirdNightly(Nightly):
    appName = 'thunderbird'
    name = 'thunderbird'
    profileClass = ThunderbirdProfile

    def getRepoName(self, date):
        # sneaking this in here
        if get_platform()['name'] == "Windows" and date < datetime.date(2010, 03, 18):
           # no .zip package for Windows, can't use the installer
           print "Can't run Windows builds before 2010-03-18"
           sys.exit()

        if date < datetime.date(2008, 7, 26):
            return "trunk"
        elif date < datetime.date(2009, 1, 9):
            return "comm-central"
        elif date < datetime.date(2010, 8, 21):
            return "comm-central-trunk"
        else:
            return "comm-central"


class FirefoxNightly(Nightly):
    appName = 'firefox'
    name = 'firefox'
    profileClass = FirefoxProfile

    def getRepoName(self, date):
        if date < datetime.date(2008, 6, 17):
            return "trunk"
        else:
            return "mozilla-central"

class FennecNightly(Nightly):
    appName = 'mobile'
    name = 'fennec'
    profileClass = FirefoxProfile

    def __init__(self, repo_name=None):
        Nightly.__init__(self, repo_name)
        self.buildRegex = 'fennec-.*\.apk'
        self.processName = 'org.mozilla.fennec'
        self.binary = 'org.mozilla.fennec/.App'
        if "y" != raw_input("WARNING: bisecting nightly fennec builds will clobber your existing nightly profile. Continue? (y or n)"):
            raise Exception("Aborting!")

    def getRepoName(self, date):
        return "mozilla-central-android"

    def install(self):
        subprocess.check_call(["adb", "uninstall", "org.mozilla.fennec"])
        subprocess.check_call(["adb", "install", self.dest])
        return True

    def start(self, profile, addons, cmdargs):
        subprocess.check_call(["adb", "shell", "am start -n %s" % self.binary])
        return True

    def stop(self):
        # TODO: kill fennec (don't really care though since uninstalling it kills it)
        # PID = $(adb shell ps | grep org.mozilla.fennec | awk '{ print $2 }')
        # adb shell run-as org.mozilla.fennec kill $PID
        return True

class NightlyRunner(object):
    apps = {'thunderbird': ThunderbirdNightly,
            'fennec': FennecNightly,
            'firefox': FirefoxNightly}

    def __init__(self, addons=None, appname="firefox", repo_name=None,
                 profile=None, cmdargs=()):
        self.app = self.apps[appname](repo_name=repo_name)
        self.addons = addons
        self.profile = profile
        self.cmdargs = list(cmdargs)

    def install(self, date=datetime.date.today()):
        if not self.app.download(date=date):
            print "Could not find nightly from %s" % date
            return False # download failed
        print "Installing nightly"
        return self.app.install()

    def start(self, date=datetime.date.today()):
        if not self.install(date):
            return False
        print "Starting nightly"
        if not self.app.start(self.profile, self.addons, self.cmdargs):
            return False
        return True

    def stop(self):
        self.app.stop()

    def wait(self):
        self.app.wait()

    def cleanup(self):
        self.app.cleanup()

    def getAppInfo(self):
        return self.app.getAppInfo()

def cli(args=sys.argv[1:]):
    """moznightly command line entry point"""

    # parse command line options
    parser = OptionParser()
    parser.add_option("-d", "--date", dest="date", help="date of the nightly",
                      metavar="YYYY-MM-DD", default=str(datetime.date.today()))
    parser.add_option("-a", "--addons", dest="addons",
                      help="list of addons to install",
                      metavar="PATH1,PATH2")
    parser.add_option("-p", "--profile", dest="profile", help="path to profile to user", metavar="PATH")
    parser.add_option("-n", "--app", dest="app", help="application name",
                      type="choice",
                      metavar="[%s]" % "|".join(NightlyRunner.apps.keys()),
                      choices=NightlyRunner.apps.keys(),
                      default="firefox")
    parser.add_option("-r", "--repo", dest="repo_name", help="repository name on ftp.mozilla.org",
                      metavar="[tracemonkey|mozilla-1.9.2]", default=None)
    options, args = parser.parse_args(args)
    # XXX https://github.com/mozilla/mozregression/issues/50
    addons = strsplit(options.addons or "", ",")

    # run nightly
    runner = NightlyRunner(appname=options.app, addons=addons,
                           profile=options.profile, repo_name=options.repo_name)
    runner.start(get_date(options.date))
    try:
        runner.wait()
    except KeyboardInterrupt:
        runner.stop()


if __name__ == "__main__":
    cli()
