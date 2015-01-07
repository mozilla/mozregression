#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Define the launcher classes, responsible of running the tested applications.
"""

from mozlog.structured import get_default_logger
from mozprofile import FirefoxProfile, ThunderbirdProfile, Profile
from mozrunner import Runner
from mozfile import rmtree
from mozdevice import ADBAndroid, ADBHost
import mozversion
import mozinstall
import tempfile
import os

from mozregression.utils import ClassRegistry, download_url, yes_or_exit


class Launcher(object):
    """
    Handle the logic of downloading a build file, installing and
    running an application.
    """
    def __init__(self, url, persist=None, persist_prefix=''):
        self._running = False
        self._logger = get_default_logger('Test Runner')

        basename = os.path.basename(url)
        if persist:
            dest = os.path.join(persist, '%s%s' % (persist_prefix, basename))
            if not os.path.exists(dest):
                self._download(url, dest)
            else:
                self._logger.info("Using local file: %s" % dest)
        else:
            dest = basename
            self._download(url, dest)

        try:
            self._install(dest)
        finally:
            if not persist:
                os.unlink(dest)

    def start(self, **kwargs):
        """
        Start the application.
        """
        if not self._running:
            self._start(**kwargs)
            self._running = True

    def stop(self):
        """
        Stop the application.
        """
        if self._running:
            self._stop()
            self._running = False

    def get_app_info(self):
        """
        Return information about the application.
        """
        if self._running:
            return self._get_app_info()

    def __del__(self):
        self.stop()

    def _download(self, url, dest):
        self._logger.info("Downloading build from: %s" % url)
        download_url(url, dest)

    def _get_app_info(self):
        raise NotImplementedError

    def _install(self, dest):
        raise NotImplementedError

    def _start(self, **kwargs):
        raise NotImplementedError

    def _stop(self):
        raise NotImplementedError


class MozRunnerLauncher(Launcher):
    tempdir = None
    runner = None
    app_name = 'undefined'
    profile_class = Profile
    binary = None

    def _install(self, dest):
        self.tempdir = tempfile.mkdtemp()
        self.binary = mozinstall.get_binary(
            mozinstall.install(src=dest, dest=self.tempdir),
            self.app_name)

    def _start(self, profile=None, addons=(), cmdargs=()):
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

    def _stop(self):
        self.runner.stop()

    def __del__(self):
        try:
            Launcher.__del__(self)
        finally:
            # always remove tempdir
            if self.tempdir is not None:
                rmtree(self.tempdir)

    def _get_app_info(self):
        return mozversion.get_version(binary=self.binary)


REGISTRY = ClassRegistry('app_name')


def create_launcher(name, url, persist=None, persist_prefix=''):
    """
    Create and returns an instance launcher for the given name.
    """
    return REGISTRY.get(name)(url,
                              persist=persist,
                              persist_prefix=persist_prefix)


@REGISTRY.register('firefox')
class FirefoxLauncher(MozRunnerLauncher):
    profile_class = FirefoxProfile


@REGISTRY.register('thunderbird')
class ThunderbirdLauncher(MozRunnerLauncher):
    profile_class = ThunderbirdProfile


@REGISTRY.register('b2g')
class B2GLauncher(MozRunnerLauncher):
    pass


@REGISTRY.register('fennec')
class FennecLauncher(Launcher):
    app_info = None

    def _install(self, dest):
        while not ADBHost().devices():
            yes_or_exit("WARNING: no device connected. Connect a device"
                        " and try again.\nTry again?")

        self.adb = ADBAndroid()
        yes_or_exit("WARNING: bisecting nightly fennec builds will clobber"
                    " your existing nightly profile. Continue?")

        self.adb.uninstall_app("org.mozilla.fennec")
        self.adb.install_app(dest)
        # get info now, as dest may be removed
        self.app_info = mozversion.get_version(binary=dest)

    def _start(self, **kwargs):
        self.adb.launch_fennec("org.mozilla.fennec")

    def _stop(self):
        self.adb.stop_application("org.mozilla.fennec")

    def _get_app_info(self):
        return self.app_info
