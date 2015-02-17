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

from mozregression.utils import ClassRegistry, download_url
from mozregression.errors import LauncherNotRunnable


class Launcher(object):
    """
    Handle the logic of downloading a build file, installing and
    running an application.
    """

    @classmethod
    def check_is_runnable(cls):
        """
        Check that the launcher can be created and can run on the system.

        :raises: :class:`LauncherNotRunnable`.
        """
        pass

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
        raise NotImplementedError

    def __del__(self):
        self.stop()

    def _download(self, url, dest):
        self._logger.info("Downloading build from: %s" % url)
        download_url(url, dest)

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

    def get_app_info(self):
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
    adb = None

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
        if not raw_input("WARNING: bisecting fennec builds will clobber your"
                         " existing profile. Type 'y' to continue:") == 'y':
            raise LauncherNotRunnable('Aborted.')

    def _install(self, dest):
        self.adb = ADBAndroid()
        self.adb.uninstall_app("org.mozilla.fennec")
        self.adb.install_app(dest)
        # get info now, as dest may be removed
        self.app_info = mozversion.get_version(binary=dest)

    def _start(self, **kwargs):
        self.adb.launch_fennec("org.mozilla.fennec")

    def _stop(self):
        self.adb.stop_application("org.mozilla.fennec")

    def get_app_info(self):
        return self.app_info
