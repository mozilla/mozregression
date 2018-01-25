# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Define the launcher classes, responsible of running the tested applications.
"""

import os
import time
from mozlog.structured import get_default_logger, get_proxy_logger
from mozprofile import ThunderbirdProfile, Profile
from mozrunner import Runner
from mozfile import rmtree
from mozdevice import ADBAndroid, ADBHost, ADBError
import mozversion
import mozinstall
import zipfile
import mozinfo
import stat
from subprocess import call
from abc import ABCMeta, abstractmethod
from threading import Thread

from mozregression.class_registry import ClassRegistry
from mozregression.errors import LauncherNotRunnable, LauncherError
from mozregression.tempdir import safe_mkdtemp

LOG = get_proxy_logger("Test Runner")


class Launcher:
    """
    Handle the logic of downloading a build file, installing and
    running an application.
    """
    __metaclass__ = ABCMeta
    profile_class = Profile

    @classmethod
    def check_is_runnable(cls):
        """
        Check that the launcher can be created and can run on the system.

        :raises: :class:`LauncherNotRunnable`.
        """
        pass

    def __init__(self, dest, **kwargs):
        self._running = False
        self._stopping = False

        try:
            self._install(dest)
        except Exception:
            msg = "Unable to install %r" % dest
            LOG.error(msg, exc_info=True)
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
                LOG.error(msg, exc_info=True)
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
                LOG.error(msg, exc_info=True)
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

    @abstractmethod
    def _install(self, dest):
        raise NotImplementedError

    @abstractmethod
    def _start(self, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def _wait(self):
        raise NotImplementedError

    @abstractmethod
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
            if not os.path.exists(profile):
                LOG.warning(
                    "Creating directory '%s' to put the profile in there"
                    % profile
                )
                os.makedirs(profile)
                # since the user gave an empty dir for the profile,
                # let's keep it on the disk in any case.
                clone = False
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


def safe_get_version(**kwargs):
    # some really old firefox builds are not supported by mozversion
    # and let's be paranoid and handle any error (but report them!)
    try:
        return mozversion.get_version(**kwargs)
    except mozversion.VersionError, exc:
        LOG.warning("Unable to get app version: %s" % exc)
        return {}


class MozRunnerLauncher(Launcher):
    tempdir = None
    runner = None
    app_name = 'undefined'
    binary = None

    def _install(self, dest):
        self.tempdir = safe_mkdtemp()
        try:
            self.binary = mozinstall.get_binary(
                mozinstall.install(src=dest, dest=self.tempdir),
                self.app_name
            )
        except Exception:
            rmtree(self.tempdir)
            raise

    def _start(self, profile=None, addons=(), cmdargs=(), preferences=None):
        profile = self._create_profile(profile=profile, addons=addons,
                                       preferences=preferences)

        LOG.info("Launching %s" % self.binary)
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
                    LOG.error(
                        "Error while waiting process, consider filing a bug.",
                        exc_info=True
                    )
                    return
                if exitcode != 0:
                    # first print a blank line, to be sure we don't
                    # write on an already printed line without EOL.
                    print
                    LOG.warning('Process exited with code %s' % exitcode)

        self.runner.process_args = {
            'processOutputLine': [get_default_logger("process").info],
            'onFinish': _on_exit,
        }
        self.runner.start()

    def _wait(self):
        return self.runner.wait()

    def _stop(self):
        if mozinfo.os == "win" and self.app_name == 'firefox':
            # for some reason, stopping the runner may hang on windows. For
            # example restart the browser in safe mode, it will hang for a
            # couple of minutes. As a workaround, we call that in a thread and
            # wait a bit for the completion. If the stop() can't complete we
            # forgot about that thread.
            thread = Thread(target=self.runner.stop)
            thread.daemon = True
            thread.start()
            thread.join(0.7)
        else:
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
        return safe_get_version(binary=self.binary)


REGISTRY = ClassRegistry('app_name')


def create_launcher(buildinfo):
    """
    Create and returns an instance launcher for the given buildinfo.
    """
    return REGISTRY.get(buildinfo.app_name)(
        buildinfo.build_file,
        task_id=buildinfo.task_id
    )


class FirefoxRegressionProfile(Profile):
    """
    Specialized Profile subclass for Firefox / Fennec

    Some preferences may only apply to one or the other
    """

    preferences = {  # Don't automatically update the application
        'app.update.enabled': False,
        # Don't restore the last open set of tabs
        # if the browser has crashed
        'browser.sessionstore.resume_from_crash': False,
        # Don't check for the default web browser during startup
        'browser.shell.checkDefaultBrowser': False,
        # Don't warn on exit when multiple tabs are open
        'browser.tabs.warnOnClose': False,
        # Don't warn when exiting the browser
        'browser.warnOnQuit': False,
        # Don't send Firefox health reports to the production
        # server
        'datareporting.healthreport.uploadEnabled': False,
        'datareporting.healthreport.documentServerURI':
        'http://%(server)s/healthreport/',
        # Don't show tab with privacy notice on every launch
        'datareporting.policy.dataSubmissionPolicyBypassNotification': True,
        # Don't report telemetry information
        'toolkit.telemetry.enabled': False,
        # Allow sideloading extensions
        'extensions.autoDisableScopes': 0,
    }


@REGISTRY.register('firefox')
class FirefoxLauncher(MozRunnerLauncher):
    profile_class = FirefoxRegressionProfile


@REGISTRY.register('thunderbird')
class ThunderbirdLauncher(MozRunnerLauncher):
    profile_class = ThunderbirdProfile


@REGISTRY.register('fennec')
class FennecLauncher(Launcher):
    app_info = None
    adb = None
    package_name = None
    profile_class = FirefoxRegressionProfile
    remote_profile = None

    @classmethod
    def check_is_runnable(cls):
        try:
            devices = ADBHost().devices()
        except ADBError as adb_error:
            raise LauncherNotRunnable(str(adb_error))
        if not devices:
            raise LauncherNotRunnable("No android device connected."
                                      " Connect a device and try again.")

    def _install(self, dest):
        # get info now, as dest may be removed
        self.app_info = safe_get_version(binary=dest)
        self.package_name = self.app_info.get("package_name",
                                              "org.mozilla.fennec")
        self.adb = ADBAndroid()
        try:
            self.adb.uninstall_app(self.package_name)
        except ADBError, msg:
            LOG.warning(
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
        LOG.debug("Pushing profile to device (%s -> %s)" % (
            profile.profile, self.remote_profile))
        self.adb.push(profile.profile, self.remote_profile)

        LOG.debug("Launching fennec")
        self.adb.launch_fennec(self.package_name,
                               extra_args=["-profile", self.remote_profile])

    def _wait(self):
        while self.adb.process_exist(self.package_name):
            time.sleep(0.1)

    def _stop(self):
        self.adb.stop_application(self.package_name)
        if self.adb.exists(self.remote_profile):
            self.adb.rm(self.remote_profile, recursive=True)

    def get_app_info(self):
        return self.app_info


@REGISTRY.register('jsshell')
class JsShellLauncher(Launcher):
    temp_dir = None

    def _install(self, dest):
        self.tempdir = safe_mkdtemp()
        try:
            with zipfile.ZipFile(dest, "r") as z:
                z.extractall(self.tempdir)
            self.binary = os.path.join(
                self.tempdir,
                'js' if mozinfo.os != 'win' else 'js.exe'
            )
            # set the file executable
            os.chmod(self.binary, os.stat(self.binary).st_mode | stat.S_IEXEC)
        except Exception:
            rmtree(self.tempdir)
            raise

    def _start(self, **kwargs):
        LOG.info("Launching %s" % self.binary)
        res = call([self.binary], cwd=self.tempdir)
        if res != 0:
            LOG.warning('jsshell exited with code %d.' % res)

    def _wait(self):
        pass

    def _stop(self, **kwargs):
        pass

    def get_app_info(self):
        return {}

    def cleanup(self):
        try:
            Launcher.cleanup(self)
        finally:
            # always remove tempdir
            if self.tempdir is not None:
                rmtree(self.tempdir)
