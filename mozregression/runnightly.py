#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import os
import mozinstall
import re
import subprocess
import sys
import tempfile
import mozinfo
import zipfile

from mozfile import rmtree
from mozprofile import FirefoxProfile
from mozprofile import ThunderbirdProfile
from mozrunner import Runner
from optparse import OptionParser
from utils import strsplit, get_date, download_url, urlLinks
from ConfigParser import ConfigParser

subprocess._cleanup = lambda : None # mikeal's fix for subprocess threading bug
# XXX please reference this issue with a URL!

class Nightly(object):

    name = None # abstract base class
    _monthlinks = {}
    lastdest = None
    tempdir = None

    @staticmethod
    def _getBuildRegex(bits):
        if mozinfo.os == "win":
            if bits == 64:
                # XXX this should actually throw an error to be consumed by the caller
                print "No builds available for 64 bit Windows (try specifying --bits=32)"
                sys.exit()
            return ".*win32.zip"
        elif mozinfo.os == "linux":
            if bits == 64:
                return ".*linux-x86_64.tar.bz2"
            else:
                return ".*linux-i686.tar.bz2"
        elif mozinfo.os == "mac":
            return ".*mac.*\.dmg"

    def __init__(self, repo_name=None, bits=mozinfo.bits, persist=None):
        self.buildRegex = self._getBuildRegex(bits)
        self.persist = persist
        self.repo_name = repo_name

    ### cleanup functions

    def remove_tempdir(self):
        if self.tempdir:
            rmtree(self.tempdir)
            self.tempdir = None

    def remove_lastdest(self):
        if self.lastdest:
            os.remove(self.lastdest)
            self.lastdest = None

    def cleanup(self):
        self.remove_tempdir()
        if not self.persist:
            self.remove_lastdest()

    __del__ = cleanup

    ### installation functions

    def get_destination(self, url, date):
        repo_name = self.repo_name or self.getRepoName(date)
        dest = os.path.basename(url)
        if self.persist is not None:
            date_str = date.strftime("%Y-%m-%d")
            dest = os.path.join(self.persist, "%s--%s--%s"%(date_str, repo_name, dest))
        return dest

    def download(self, date=datetime.date.today(), dest=None):
        url = self.getBuildUrl(date)
        if url:
            if not dest:
                dest = self.get_destination(url, date)
            if not self.persist:
                self.remove_lastdest()

            self.dest = self.lastdest = dest
            download_url(url, dest)
            return True
        else:
            return False

    def install(self):
        if not self.name:
            raise NotImplementedError("Can't invoke abstract base class")
        self.remove_tempdir()
        self.tempdir = tempfile.mkdtemp()
        self.binary = mozinstall.get_binary(mozinstall.install(src=self.dest, dest=self.tempdir), self.name)
        return True

    def getBuildUrl(self, datestamp):
        if self.appName == 'fennec':
            repo = 'mobile'
        else:
            repo = 'firefox'
        url = "http://ftp.mozilla.org/pub/mozilla.org/" + repo + "/nightly/"
        year = str(datestamp.year)
        month = "%02d" % datestamp.month
        day = "%02d" % datestamp.day
        repo_name = self.repo_name or self.getRepoName(datestamp)
        url += year + "/" + month + "/"

        linkRegex = '^' + year + '-' + month + '-' + day + '-' + '[\d-]+' + repo_name + '/$'
        cachekey = year + '-' + month
        if cachekey in self._monthlinks:
            monthlinks = self._monthlinks[cachekey]
        else:
            monthlinks = urlLinks(url)
            self._monthlinks[cachekey] = monthlinks

        # first parse monthly list to get correct directory
        for dirlink in monthlinks:
            dirhref = dirlink.get("href")
            if re.match(linkRegex, dirhref):
                # now parse the page for the correct build url
                for link in urlLinks(url + dirhref):
                    href = link.get("href")
                    if re.match(self.buildRegex, href):
                        return url + dirhref + href

    ### functions for invoking nightly

    def getAppInfo(self):
        parser = ConfigParser()
        ini_file = os.path.join(os.path.dirname(self.binary), "application.ini")
        parser.read(ini_file)
        try:
            changeset = parser.get('App', 'SourceStamp')
            repo = parser.get('App', 'SourceRepository')
            return (repo, changeset)
        except:
            return None

    def start(self, profile, addons, cmdargs):
        if profile:
            profile = self.profileClass(profile=profile, addons=addons)
        elif len(addons):
            profile = self.profileClass(addons=addons)
        else:
            profile = self.profileClass()

        self.runner = Runner(binary=self.binary, cmdargs=cmdargs, profile=profile)
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
        if mozinfo.os == "win" and date < datetime.date(2010, 03, 18):
           # no .zip package for Windows, can't use the installer
           print "Can't run Windows builds before 2010-03-18"
           sys.exit()
           # XXX this should throw an exception vs exiting without the error code

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
    appName = 'fennec'
    name = 'fennec'
    profileClass = FirefoxProfile
    buildRegex = 'fennec-.*\.apk'
    binary = 'org.mozilla.fennec/.App'
    bits = None

    def __init__(self, repo_name=None, bits=mozinfo.bits, persist=None):
        self.repo_name = repo_name
        self.persist = persist
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

    def getAppInfo(self):
        archive = zipfile.ZipFile(self.dest, 'r')
        f = archive.open('application.ini')
        parser = ConfigParser()
        parser.readfp(f)
        try:
            changeset = parser.get('App', 'SourceStamp')
            repo = parser.get('App', 'SourceRepository')
            return (repo, changeset)
        except:
            return None

class NightlyRunner(object):

    apps = {'thunderbird': ThunderbirdNightly,
            'fennec': FennecNightly,
            'firefox': FirefoxNightly}

    def __init__(self, addons=None, appname="firefox", repo_name=None,
                 profile=None, cmdargs=(), bits=mozinfo.bits, persist=None):
        self.app = self.apps[appname](repo_name=repo_name, bits=bits, persist=persist)
        self.addons = addons
        self.profile = profile
        self.persist = persist
        self.cmdargs = list(cmdargs)

    def install(self, date=datetime.date.today()):
        if not self.app.download(date=date):
            print "Could not find build from %s" % date
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

def parseBits(optionBits):
    """returns the correctly typed bits"""
    if optionBits == "32":
        return 32
    else:
        # if 64 bits is passed on a 32 bit system, it won't be honored
        return mozinfo.bits

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
    parser.add_option("--bits", dest="bits", help="force 32 or 64 bit version (only applies to x86_64 boxes)",
                      choices=("32","64"), default=mozinfo.bits)
    parser.add_option("--persist", dest="persist", help="the directory in which files are to persist ie. /Users/someuser/Documents")
    options, args = parser.parse_args(args)

    options.bits = parseBits(options.bits)

    # XXX https://github.com/mozilla/mozregression/issues/50
    addons = strsplit(options.addons or "", ",")

    # run nightly
    runner = NightlyRunner(appname=options.app, addons=addons,
                           profile=options.profile, repo_name=options.repo_name, bits=options.bits,
                           persist=options.persist)
    runner.start(get_date(options.date))
    try:
        runner.wait()
    except KeyboardInterrupt:
        runner.stop()


if __name__ == "__main__":
    cli()
