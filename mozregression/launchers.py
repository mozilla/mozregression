#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Define the launcher classes, responsible of running the tested applications.
"""

import os
import time
from mozlog.structured import get_default_logger
from mozprofile import FirefoxProfile, ThunderbirdProfile, Profile
from mozrunner import Runner
from mozfile import rmtree
from mozdevice import ADBAndroid, ADBHost, ADBError
import mozversion
import mozinstall
import tempfile

from mozregression.class_registry import ClassRegistry
from mozregression.errors import LauncherNotRunnable, LauncherError


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
        self._stopping = False
        self._logger = get_default_logger('Test Runner')

        try:
            self._install(dest)
        except Exception:
            msg = "Unable to install %r" % dest
            self._logger.error(msg, exc_info=True)
            raise LauncherError(msg)

    def start(self, **kwargs):
        """
        Start the application.
        """
        if not self._running:
            try:
                self._start(**kwargs)
            except Exception:
                msg = "Unable to start the application"
                self._logger.error(msg, exc_info=True)
                raise LauncherError(msg)
            self._running = True

    def wait(self):
        """
        Wait for the application to be finished and return the error code
        when available.
        """
        if self._running:
            return_code = self._wait()
            self.stop()
            return return_code

    def stop(self):
        """
        Stop the application.
        """
        if self._running:
            self._stopping = True
            try:
                self._stop()
            except Exception:
                msg = "Unable to stop the application"
                self._logger.error(msg, exc_info=True)
                raise LauncherError(msg)
            self._running = False
            self._stopping = False

    def get_app_info(self):
        """
        Return information about the application.
        """
        raise NotImplementedError

    def cleanup(self):
        self.stop()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cleanup()

    def _install(self, dest):
        raise NotImplementedError

    def _start(self, **kwargs):
        raise NotImplementedError

    def _wait(self):
        raise NotImplementedError

    def _stop(self):
        raise NotImplementedError

    def _create_profile(self, profile=None, addons=(), preferences=None):
        if isinstance(profile, Profile):
            return profile
        else:
            return self.create_profile(profile=profile, addons=addons,
                                       preferences=preferences)

    @classmethod
    def create_profile(cls, profile=None, addons=(), preferences=None,
                       clone=True):
        if profile:
            if clone:
                # mozprofile makes some changes in the profile that can not
                # be undone. Let's clone the profile to not have side effect
                # on existing profile.
                # see https://bugzilla.mozilla.org/show_bug.cgi?id=999009
                profile = cls.profile_class.clone(profile, addons=addons,
                                                  preferences=preferences)
            else:
                profile = cls.profile_class(profile, addons=addons,
                                            preferences=preferences)
        elif len(addons):
            profile = cls.profile_class(addons=addons,
                                        preferences=preferences)
        else:
            profile = cls.profile_class(preferences=preferences)
        return profile


class MozRunnerLauncher(Launcher):
    tempdir = None
    runner = None
    app_name = 'undefined'
    binary = None

    def _install(self, dest):
        self.tempdir = tempfile.mkdtemp()
        try:
            self.binary = mozinstall.get_binary(
                mozinstall.install(src=dest, dest=self.tempdir),
                self.app_name
            )
        except:
            rmtree(self.tempdir)
            raise

    def _start(self, profile=None, addons=(), cmdargs=(), preferences=None):
        profile = self._create_profile(profile=profile, addons=addons,
                                       preferences=preferences)

        self._logger.info("Launching %s" % self.binary)
        self.runner = Runner(binary=self.binary,
                             cmdargs=cmdargs,
                             profile=profile)

        def _on_exit():
            # if we are stopping the process do not log anything.
            if not self._stopping:
                # mozprocess (behind mozrunner) fire 'onFinish'
                # a bit early - let's ensure the process is finished.
                # we have to call wait() directly on the subprocess
                # instance of the ProcessHandler, else on windows
                # None is returned...
                # TODO: search that bug and fix that in mozprocess or
                # mozrunner. (likely mozproces)
                try:
                    exitcode = self.runner.process_handler.proc.wait()
                except Exception:
                    print
                    self._logger.error(
                        "Error while waiting process, consider filing a bug.",
                        exc_info=True
                    )
                    return
                if exitcode != 0:
                    # first print a blank line, to be sure we don't
                    # write on an already printed line without EOL.
                    print
                    self._logger.warning('Process exited with code %s'
                                         % exitcode)

        self.runner.process_args = {
            'processOutputLine': [self._logger.debug],
            'onFinish': _on_exit,
        }
        self.runner.start()

    def _wait(self):
        return self.runner.wait()

    def _stop(self):
        self.runner.stop()
        # release the runner since it holds a profile reference
        del self.runner

    def cleanup(self):
        try:
            Launcher.cleanup(self)
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
        try:
            self.adb.uninstall_app(self.package_name)
        except ADBError, msg:
            self._logger.warning(
                "Failed to uninstall %s (%s)\nThis is normal if it is the"
                " first time the application is installed."
                % (self.package_name, msg)
            )
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

    def _wait(self):
        while self.adb.process_exist():
            time.sleep(0.1)

    def _stop(self):
        self.adb.stop_application(self.package_name)
        if self.adb.exists(self.remote_profile):
            self.adb.rm(self.remote_profile, recursive=True)

    def get_app_info(self):
        return self.app_info
