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

    def __del__(self):
        # cleanup
        rmdirRecursive('moznightlyapp')
        if self.lastdest:
            os.remove(self.lastdest)

    def download(self, date=datetime.date.today(), dest=None):
        url = self.getBuildUrl(date)
        if url:
            if not dest:
                dest = os.path.basename(url)
            print "\nDownloading nightly from " + str(date) + "\n"
            if self.lastdest:
                os.remove(self.lastdest)
            download_url(url, dest)
            self.dest = self.lastdest = dest
            return True
        else:
            return False

    def install(self):
        rmdirRecursive("moznightlyapp")
        subprocess._cleanup = lambda : None # mikeal's fix for subprocess threading bug
        MozInstaller(src=self.dest, dest="moznightlyapp", dest_app="Mozilla.app")

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
        month = self.formatDatePart(date.month)
        day = self.formatDatePart(date.day)
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

    def formatDatePart(self, part):
        if part < 10:
            part = "0" + str(part)
        return str(part)

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

    def getRepoName(self, date):
      return "mozilla-central-linux"

class NightlyRunner(object):
    def __init__(self, addons=None, appname="firefox", repo_name=None,
                 profile=None, cmdargs=[]):
        if appname.lower() == 'thunderbird':
           self.app = ThunderbirdNightly(repo_name=repo_name)
        elif appname.lower() == 'mobile':
           self.app = FennecNightly(repo_name=repo_name)
        else:
           self.app = FirefoxNightly(repo_name=repo_name)
        self.addons = addons
        self.profile = profile
        self.cmdargs = cmdargs

    def install(self, date=datetime.date.today()):
        if not self.app.download(date=date):
            print "could not find nightly from " + str(date)
            return False # download failed
        print "Starting nightly\n"
        self.app.install()

    def start(self, date=datetime.date.today()):
        self.install(date)
        if self.profile:
            profile = self.app.profileClass(profile=self.profile, addons=self.addons)
        elif len(self.addons):
            profile = self.app.profileClass(addons=self.addons)
        else:
            profile = self.app.profileClass()

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
    parser.add_option("-r", "--repo", dest="repo_name", help="repository name on ftp.mozilla.org",
                      metavar="[tracemonkey|mozilla-1.9.2]", default=None)
    (options, args) = parser.parse_args()

    runner = NightlyRunner(appname=options.app, addons=strsplit(options.addons, ","),
                           profile=options.profile, repo_name=options.repo_name)
    runner.start(get_date(options.date))


if __name__ == "__main__":
    cli()
