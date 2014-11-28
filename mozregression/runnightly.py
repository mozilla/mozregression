#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import os
import mozinstall
import re
import sys
import tempfile
import mozinfo
from mozfile import rmtree
from mozprofile import FirefoxProfile, ThunderbirdProfile, Profile
from mozrunner import Runner
from optparse import OptionParser
import mozversion
import requests
from mozlog.structured import get_default_logger

from mozregression import errors
from mozregression.utils import (parse_date, download_url, url_links,
                                 get_build_regex, parse_bits)

from mozdevice import ADBAndroid, ADBHost

class Nightly(object):

    name = None  # abstract base class
    _monthlinks = {}
    lastdest = None
    tempdir = None
    app_name = None
    profile_class = Profile
    build_base_repo_name = "firefox"

    def __init__(self, inbound_branch=None, bits=mozinfo.bits, persist=None):
        self.inbound_branch = inbound_branch
        self.bits = bits
        self.persist = persist
        os = mozinfo.os
        self.build_regex = get_build_regex(self.name, os, bits) + "$"
        self.build_info_regex = \
            get_build_regex(self.name, os, bits, with_ext=False) + "\.txt$"
        self._logger = get_default_logger('Regression Runner')

    def get_inbound_branch(self, date):
        raise NotImplementedError

    # cleanup functions

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

    # installation functions

    def get_destination(self, url, date):
        inbound_branch = self.get_inbound_branch(date)
        dest = os.path.basename(url)
        if self.persist is not None:
            if hasattr(date, "strftime"):
                date_str = date.strftime("%Y-%m-%d")
            else:
                date_str = date  # Might be just a number with inbound
            dest = os.path.join(self.persist,
                                "%s--%s--%s" % (date_str, inbound_branch, dest))
        return dest

    def download(self, date=datetime.date.today(), dest=None):
        url = self.get_build_url(date)
        if url:
            if not dest:
                dest = self.get_destination(url, date)
            if not self.persist:
                self.remove_lastdest()

            if os.path.exists(dest):
                self._logger.info("Using local file: %s" % dest)
            else:
                self._logger.info("Downloading build from: %s" % url)
                download_url(url, dest)
            self.dest = self.lastdest = dest
            return True
        else:
            return False

    def install(self):
        if not self.name:
            raise NotImplementedError("Can't invoke abstract base class")
        self.remove_tempdir()
        self.tempdir = tempfile.mkdtemp()
        self.binary = mozinstall.get_binary(
            mozinstall.install(src=self.dest, dest=self.tempdir),
            self.name)
        return True

    def get_build_info(self, date):
        url = self._get_build_url(date, self.build_info_regex, 'builds info')
        if url is not None:
            self._logger.info("Getting %s" % url)
            response = requests.get(url)
            if response.status_code == 200:
                for line in response.text.splitlines():
                    if '/rev/' in line:
                        # returns [repository, changeset]
                        return line.split('/rev/')

    def get_build_url(self, datestamp):
        return self._get_build_url(datestamp, self.build_regex, 'builds')

    def _get_build_url(self, datestamp, regex, what):
        url = "http://ftp.mozilla.org/pub/mozilla.org/" + \
            self.build_base_repo_name + "/nightly/"
        year = str(datestamp.year)
        month = "%02d" % datestamp.month
        day = "%02d" % datestamp.day
        inbound_branch = self.get_inbound_branch(datestamp)
        url += year + "/" + month + "/"

        link_regex = '^' + year + '-' + month + '-' + day + '-' \
                     + r'[\d-]+' + inbound_branch + '/$'
        cachekey = year + '-' + month
        if cachekey in self._monthlinks:
            monthlinks = self._monthlinks[cachekey]
        else:
            monthlinks = url_links(url)
            self._monthlinks[cachekey] = monthlinks

        # first parse monthly list to get correct directory
        matches = []
        for dirlink in monthlinks:
            if re.match(link_regex, dirlink):
                # now parse the page for the correct build url
                for link in url_links(url + dirlink, regex=regex):
                    matches.append(url + dirlink + link)
        if not matches:
            self._logger.info("Tried to get %s from %s that match '%s'"
                              " but didn't find any."
                              % (what, url, self.build_regex))
            return None
        else:
            return sorted(matches)[-1] # the most recent build url

    # functions for invoking nightly

    def get_app_info(self):
        return mozversion.get_version(binary=self.binary)

    def start(self, profile, addons, cmdargs):
        if profile:
            profile = self.profile_class(profile=profile, addons=addons)
        elif len(addons):
            profile = self.profile_class(addons=addons)
        else:
            profile = self.profile_class()

        process_args = {'processOutputLine': [self._logger.debug]}
        self.runner = Runner(binary=self.binary,
                             cmdargs=cmdargs,
                             profile=profile,
                             process_args=process_args)
        self.runner.start()
        return True

    def stop(self):
        self.runner.stop()

    def wait(self):
        self.runner.wait()


class ThunderbirdNightly(Nightly):
    app_name = 'thunderbird'
    name = 'thunderbird'
    build_base_repo_name = 'thunderbird'
    profile_class = ThunderbirdProfile

    def get_inbound_branch(self, date):
        # sneaking this in here
        if mozinfo.os == "win" and date < datetime.date(2010, 03, 18):
            # no .zip package for Windows, can't use the installer
            raise errors.WinTooOldBuildError()

        if date < datetime.date(2008, 7, 26):
            return "trunk"
        elif date < datetime.date(2009, 1, 9):
            return "comm-central"
        elif date < datetime.date(2010, 8, 21):
            return "comm-central-trunk"
        else:
            return "comm-central"


class FirefoxNightly(Nightly):
    app_name = 'firefox'
    name = 'firefox'
    profile_class = FirefoxProfile

    def get_inbound_branch(self, date):
        if date < datetime.date(2008, 6, 17):
            return "trunk"
        else:
            return "mozilla-central"


class FennecNightly(Nightly):
    app_name = 'fennec'
    name = 'fennec'
    profile_class = FirefoxProfile
    binary = 'org.mozilla.fennec/.App'
    build_base_repo_name = "mobile"

    def get_device_status(self):
        self.adbhost = ADBHost()
        if self.adbhost.devices():
            return True
        if "y" == raw_input("WARNING: no device connected."
                            " Connect a device and try again.\n"
                            "Try again? (y or n): "):
            return self.get_device_status()
        raise Exception("Aborting!")

    def __init__(self, inbound_branch=None, bits=mozinfo.bits, persist=None):
        Nightly.__init__(self, inbound_branch=inbound_branch,
                               bits=bits,
                               persist=persist)
        self.build_regex = r'fennec-.*\.apk'
        self.build_info_regex = r'fennec-.*\.txt'
        if self.get_device_status():
            self.adb = ADBAndroid()
            if "y" != raw_input("WARNING: bisecting nightly fennec builds will"
                                " clobber your existing nightly profile."
                                " Continue? (y or n)"):
                raise Exception("Aborting!")

    def get_inbound_branch(self, date):
        return "mozilla-central-android"

    def install(self):
        self.adb.uninstall_app("org.mozilla.fennec")
        self.adb.install_app(self.dest)
        return True

    def start(self, profile, addons, cmdargs):
        self.adb.launch_fennec("org.mozilla.fennec")
        return True

    def stop(self):
        self.adb.stop_application("org.mozilla.fennec")
        return True

    def get_app_info(self):
        return mozversion.get_version(binary=self.dest)


class B2GNightly(Nightly):
    app_name = 'b2g'
    name = 'b2g'
    profile_class = Profile
    build_base_repo_name = 'b2g'

    def get_inbound_branch(self, date):
        return "mozilla-central"


class NightlyRunner(object):

    apps = {'thunderbird': ThunderbirdNightly,
            'fennec': FennecNightly,
            'firefox': FirefoxNightly,
            'b2g': B2GNightly}

    def __init__(self, addons=None, appname="firefox", inbound_branch=None,
                 profile=None, cmdargs=(), bits=mozinfo.bits, persist=None):
        self.app = self.apps[appname](inbound_branch=inbound_branch, bits=bits,
                                      persist=persist)
        self.addons = addons
        self.profile = profile
        self.persist = persist
        self.cmdargs = list(cmdargs)
        self.inbound_branch = inbound_branch
        self._logger = get_default_logger('Regression Runner')

    def install(self, date=datetime.date.today()):
        if not self.app.download(date=date):
            self._logger.info("Could not find build from %s" % date)
            return False  # download failed
        self._logger.info("Installing nightly")
        return self.app.install()

    def start(self, date=datetime.date.today()):
        if not self.install(date):
            return False
        info = self.get_app_info()
        if info is not None:
            self._logger.info("Starting nightly (revision: %s)"
                              % info['application_changeset'])
        else:
            self._logger.info("Starting nightly")
        if not self.app.start(self.profile, self.addons, self.cmdargs):
            return False
        return True

    def stop(self):
        self.app.stop()

    def wait(self):
        self.app.wait()

    def cleanup(self):
        self.app.cleanup()

    def get_build_info(self, date=datetime.date.today()):
        result = self.app.get_build_info(date)
        if result is None:
            self._logger.info("Failed to retrieve build repository and revision"
                              " from the build dir. Let's try to install it to"
                              " get the required metadata...")
            self.install(date)
            info = self.get_app_info()
            result = (info['application_repository'],
                      info['application_changeset'])
        return result

    def get_app_info(self):
        return self.app.get_app_info()

    def get_resume_options(self):
        info = ""
        app = self.app.app_name
        inbound_branch = self.app.inbound_branch
        bits = self.app.bits
        if app is not None:
            info += ' --app=%s' % app
        if len(self.addons) > 0:
            info += ' --addons=%s' % ",".join(self.addons)
        if self.profile is not None:
            info += ' --profile=%s' % self.profile
        if inbound_branch is not None:
            info += ' --inbound-branch=%s' % inbound_branch
        if bits is not None:
            info += ' --bits=%s' % bits
        if self.persist is not None:
            info += ' --persist=%s' % self.persist
        return info

    def print_resume_info(self, good_date_string, bad_date_string):
        self._logger.info('mozregression --good=%s --bad=%s%s'
                          % (good_date_string,
                             bad_date_string,
                             self.get_resume_options()))


def cli(args=sys.argv[1:]):
    """moznightly command line entry point"""

    # parse command line options
    parser = OptionParser()
    parser.add_option("-d", "--date", dest="date", help="date of the nightly",
                      metavar="YYYY-MM-DD", default=str(datetime.date.today()))
    parser.add_option("-a", "--addons", dest="addons",
                      help="an addon to install; repeat for multiple addons",
                      metavar="PATH1", default=[], action="append")
    parser.add_option("-p", "--profile", dest="profile",
                      help="path to profile to user", metavar="PATH")
    parser.add_option("-n", "--app", dest="app", help="application name",
                      type="choice",
                      metavar="[%s]" % "|".join(NightlyRunner.apps.keys()),
                      choices=NightlyRunner.apps.keys(),
                      default="firefox")
    parser.add_option("--inbound-branch", dest="inbound_branch",
                      help="inbound branch name on ftp.mozilla.org",
                      metavar="[tracemonkey|mozilla-1.9.2]", default=None)
    parser.add_option("--bits", dest="bits",
                      help="force 32 or 64 bit version (only applies to"
                      " x86_64 boxes)",
                      choices=("32", "64"), default=mozinfo.bits)
    parser.add_option("--persist", dest="persist",
                      help="the directory in which files are to persist ie."
                      " /Users/someuser/Documents")
    options, args = parser.parse_args(args)

    options.bits = parse_bits(options.bits)

    # run nightly
    runner = NightlyRunner(appname=options.app, addons=options.addons,
                           profile=options.profile,
                           inbound_branch=options.inbound_branch,
                           bits=options.bits, persist=options.persist)
    runner.start(parse_date(options.date))
    try:
        runner.wait()
    except KeyboardInterrupt:
        runner.stop()


if __name__ == "__main__":
    cli()
