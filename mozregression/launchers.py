#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Define the launcher classes, responsible of running the tested applications.
"""

import os
from mozlog.structured import get_default_logger
from mozprofile import FirefoxProfile, ThunderbirdProfile, Profile
from mozrunner import Runner
from mozfile import rmtree
from mozdevice import ADBAndroid, ADBHost
import mozversion
import mozinstall
import tempfile

from mozregression.utils import ClassRegistry
from mozregression.errors import LauncherNotRunnable


class Launcher(object):
    """
    Handle the logic of downloading a build file, installing and
    running an application.
    """
    profile_class = Profile

    @classmethod
    def check_is_runnable(cls):
        """
        Check that the launcher can be created and can run on the system.

        :raises: :class:`LauncherNotRunnable`.
        """
        pass

    def __init__(self, dest):
        self._running = False
        self._logger = get_default_logger('Test Runner')

        self._install(dest)

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
        raise NotImplementedError

    def __del__(self):
        self.stop()

    def _install(self, dest):
        raise NotImplementedError

    def _start(self, **kwargs):
        raise NotImplementedError

    def _stop(self):
        raise NotImplementedError

    def _create_profile(self, profile=None, addons=(), preferences=None):
        if profile:
            profile = self.profile_class(profile=profile, addons=addons,
                                         preferences=preferences)
        elif len(addons):
            profile = self.profile_class(addons=addons,
                                         preferences=preferences)
        else:
            profile = self.profile_class(preferences=preferences)
        return profile


class MozRunnerLauncher(Launcher):
    tempdir = None
    runner = None
    app_name = 'undefined'
    binary = None

    def _install(self, dest):
        self.tempdir = tempfile.mkdtemp()
        self.binary = mozinstall.get_binary(
            mozinstall.install(src=dest, dest=self.tempdir),
            self.app_name)

    def _start(self, profile=None, addons=(), cmdargs=(), preferences=None):
        profile = self._create_profile(profile=profile, addons=addons,
                                       preferences=preferences)

        self._logger.info("Launching %s" % self.binary)
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

    def get_app_info(self):
        return mozversion.get_version(binary=self.binary)


REGISTRY = ClassRegistry('app_name')


def create_launcher(name, dest):
    """
    Create and returns an instance launcher for the given name.
    """
    return REGISTRY.get(name)(dest)


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
    adb = None
    package_name = None
    remote_profile = None

    @classmethod
    def check_is_runnable(cls):
        # ADBHost().devices() seems to raise OSError when adb is not
        # installed and in PATH. TODO: maybe fix this in mozdevice.
        try:
            devices = ADBHost().devices()
        except OSError:
            raise LauncherNotRunnable("adb (Android Debug Bridge) is not"
                                      " installed or not in the PATH.")
        if not devices:
            raise LauncherNotRunnable("No android device connected."
                                      " Connect a device and try again.")

    def _install(self, dest):
        # get info now, as dest may be removed
        self.app_info = mozversion.get_version(binary=dest)
        self.package_name = self.app_info.get("package_name",
                                              "org.mozilla.fennec")
        self.adb = ADBAndroid()
        self.adb.uninstall_app(self.package_name)
        self.adb.install_app(dest)

    def _start(self, profile=None, addons=(), cmdargs=(), preferences=None):
        # for now we don't handle addons on the profile for fennec
        profile = self._create_profile(profile=profile,
                                       preferences=preferences)
        # send the profile on the device
        self.remote_profile = "/".join([self.adb.test_root,
                                       os.path.basename(profile.profile)])
        if self.adb.exists(self.remote_profile):
            self.adb.rm(self.remote_profile, recursive=True)
        self.adb.push(profile.profile, self.remote_profile)

        self.adb.launch_fennec(self.package_name,
                               extra_args=["-profile", self.remote_profile])

    def _stop(self):
        self.adb.stop_application(self.package_name)
        if self.adb.exists(self.remote_profile):
            self.adb.rm(self.remote_profile, recursive=True)

    def get_app_info(self):
        return self.app_info
