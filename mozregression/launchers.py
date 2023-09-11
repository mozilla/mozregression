"""
Define the launcher classes, responsible of running the tested applications.
"""

from __future__ import absolute_import, print_function

import hashlib
import json
import os
import stat
import subprocess
import sys
import time
import zipfile
from abc import ABCMeta, abstractmethod
from enum import Enum
from shutil import move
from subprocess import STDOUT, CalledProcessError, call, check_output
from threading import Thread

import mozinfo
import mozinstall
import mozversion
from mozdevice import ADBDeviceFactory, ADBError, ADBHost
from mozfile import remove
from mozlog.structured import get_default_logger, get_proxy_logger
from mozprofile import Profile, ThunderbirdProfile
from mozrunner import GeckoRuntimeRunner, Runner

from mozregression.class_registry import ClassRegistry
from mozregression.errors import LauncherError, LauncherNotRunnable
from mozregression.tempdir import safe_mkdtemp

LOG = get_proxy_logger("Test Runner")

# This enum is used to transform output from codesign (on macs).
CodesignResult = Enum("Result", "PASS UNSIGNED INVALID OTHER")


class Launcher(metaclass=ABCMeta):
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

    def __init__(self, dest, **kwargs):
        self._running = False
        self._stopping = False

        try:
            self._install(dest)
        except Exception as e:
            msg = "Unable to install {} (error: {})".format(dest, e)
            LOG.error(msg)
            raise LauncherError(msg).with_traceback(sys.exc_info()[2])

    def start(self, **kwargs):
        """
        Start the application.
        """
        if not self._running:
            try:
                self._start(**kwargs)
            except Exception as e:
                msg = "Unable to start the application (error: {})".format(e)
                LOG.error(msg)
                raise LauncherError(msg).with_traceback(sys.exc_info()[2])
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
            except Exception as e:
                msg = "Unable to stop the application (error: {})".format(e)
                LOG.error(msg)
                raise LauncherError(msg).with_traceback(sys.exc_info()[2])
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
            return self.create_profile(profile=profile, addons=addons, preferences=preferences)

    @classmethod
    def create_profile(cls, profile=None, addons=(), preferences=None, clone=True):
        if profile:
            if not os.path.exists(profile):
                LOG.warning("Creating directory '%s' to put the profile in there" % profile)
                os.makedirs(profile)
                # since the user gave an empty dir for the profile,
                # let's keep it on the disk in any case.
                clone = False
            if clone:
                # mozprofile makes some changes in the profile that can not
                # be undone. Let's clone the profile to not have side effect
                # on existing profile.
                # see https://bugzilla.mozilla.org/show_bug.cgi?id=999009
                profile = cls.profile_class.clone(profile, addons=addons, preferences=preferences)
            else:
                profile = cls.profile_class(profile, addons=addons, preferences=preferences)
        elif len(addons):
            profile = cls.profile_class(addons=addons, preferences=preferences)
        else:
            profile = cls.profile_class(preferences=preferences)
        return profile


def safe_get_version(**kwargs):
    # some really old firefox builds are not supported by mozversion
    # and let's be paranoid and handle any error (but report them!)
    try:
        return mozversion.get_version(**kwargs)
    except mozversion.VersionError as exc:
        LOG.warning("Unable to get app version: %s" % exc)
        return {}


class MozRunnerLauncher(Launcher):
    tempdir = None
    runner = None
    app_name = "undefined"
    binary = None

    @staticmethod
    def _codesign_verify(appdir):
        """Calls `codesign` to verify signature, and returns state."""
        if mozinfo.os != "mac":
            raise Exception("_codesign_verify should only be called on macOS.")

        try:
            output = check_output(["codesign", "-v", appdir], stderr=STDOUT)
        except CalledProcessError as e:
            output = e.output
            exit_code = e.returncode
        else:
            exit_code = 0

        LOG.debug(f"codesign verify exit code: {exit_code}")

        if exit_code == 0:
            return CodesignResult.PASS
        elif exit_code == 1:
            if b"code object is not signed at all" in output:
                # NOTE: this output message was tested on macOS 11, 12, and 13.
                return CodesignResult.UNSIGNED
            else:
                return CodesignResult.INVALID
        # NOTE: Remaining codes normally mean the command was called with incorrect
        # arguments or if there is any other unforeseen issue with running the command.
        return CodesignResult.OTHER

    @staticmethod
    def _codesign_sign(appdir):
        """Calls `codesign` to sign `appdir` with ad-hoc identity."""
        if mozinfo.os != "mac":
            raise Exception("_codesign_sign should only be called on macOS.")
        # NOTE: The `codesign` command appears to have maintained all the same
        # arguments since macOS 10, however this was tested on macOS 12.
        return call(["codesign", "--force", "--deep", "--sign", "-", appdir])

    @property
    def _codesign_invalid_on_macOS_13(self):
        """Return True if codesign verify fails on macOS 13+, otherwise return False."""
        return (
            mozinfo.os == "mac"
            and mozinfo.os_version >= "13.0"
            and self._codesign_verify(self.appdir) == CodesignResult.INVALID
        )

    def _install(self, dest):
        self.tempdir = safe_mkdtemp()
        try:
            self.binary = mozinstall.get_binary(
                mozinstall.install(src=dest, dest=self.tempdir), self.app_name
            )
        except Exception:
            remove(self.tempdir)
            raise

        self.binarydir = os.path.dirname(self.binary)
        self.appdir = os.path.normpath(os.path.join(self.binarydir, "..", ".."))
        if mozinfo.os == "mac" and self._codesign_verify(self.appdir) == CodesignResult.UNSIGNED:
            LOG.debug(f"codesign verification failed for {self.appdir}, resigning...")
            self._codesign_sign(self.appdir)

    def _disableUpdateByPolicy(self):
        updatePolicy = {"policies": {"DisableAppUpdate": True}}
        installdir = os.path.dirname(self.binary)
        if mozinfo.os == "mac":
            # macOS has the following filestructure:
            # binary at:
            #     PackageName.app/Contents/MacOS/firefox
            # we need policies.json in:
            #     PackageName.app/Contents/Resources/distribution
            installdir = os.path.normpath(os.path.join(installdir, "..", "Resources"))
        os.makedirs(os.path.join(installdir, "distribution"))
        policyFile = os.path.join(installdir, "distribution", "policies.json")
        with open(policyFile, "w") as fp:
            json.dump(updatePolicy, fp, indent=2)

    def _start(
        self,
        profile=None,
        addons=(),
        cmdargs=(),
        preferences=None,
        adb_profile_dir=None,
    ):
        profile = self._create_profile(profile=profile, addons=addons, preferences=preferences)

        LOG.info("Launching %s" % self.binary)
        self.runner = Runner(binary=self.binary, cmdargs=cmdargs, profile=profile)

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
                    print()
                    LOG.error(
                        "Error while waiting process, consider filing a bug.",
                        exc_info=True,
                    )
                    return
                if exitcode != 0:
                    # first print a blank line, to be sure we don't
                    # write on an already printed line without EOL.
                    print()
                    LOG.warning("Process exited with code %s" % exitcode)

        # we don't need stdin, and GUI will not work in Windowed mode if set
        # see: https://stackoverflow.com/a/40108817
        # also, don't stream to stdout: https://bugzilla.mozilla.org/show_bug.cgi?id=1653349
        devnull = open(os.devnull, "wb")
        self.runner.process_args = {
            "processOutputLine": [get_default_logger("process").info],
            "stdin": devnull,
            "stream": None,
            "onFinish": _on_exit,
        }
        self.runner.start()

    def _wait(self):
        return self.runner.wait()

    def _stop(self):
        if mozinfo.os == "win" and self.app_name == "firefox":
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
                remove(self.tempdir)

    def get_app_info(self):
        return safe_get_version(binary=self.binary)


REGISTRY = ClassRegistry("app_name")


def create_launcher(buildinfo, launcher_args=None):
    """
    Create and returns an instance launcher for the given buildinfo.
    """
    return REGISTRY.get(buildinfo.app_name)(
        buildinfo.build_file,
        task_id=buildinfo.task_id,
        launcher_args=launcher_args,
    )


class FirefoxRegressionProfile(Profile):
    """
    Specialized Profile subclass for Firefox / Fennec

    Some preferences may only apply to one or the other
    """

    preferences = {
        # Don't automatically update the application (only works on older
        # versions of Firefox)
        "app.update.enabled": False,
        # On newer versions of Firefox (where disabling automatic updates
        # is impossible, at least don't update automatically)
        "app.update.auto": False,
        # Don't automatically download the update (this pref is specific to
        # some versions of Fennec)
        "app.update.autodownload": "disabled",
        # Don't restore the last open set of tabs
        # if the browser has crashed
        "browser.sessionstore.resume_from_crash": False,
        # Don't check for the default web browser during startup
        "browser.shell.checkDefaultBrowser": False,
        # Don't warn on exit when multiple tabs are open
        "browser.tabs.warnOnClose": False,
        # Don't warn when exiting the browser
        "browser.warnOnQuit": False,
        # Don't send Firefox health reports to the production
        # server
        "datareporting.healthreport.uploadEnabled": False,
        "datareporting.healthreport.documentServerURI": "http://%(server)s/healthreport/",
        # Don't show tab with privacy notice on every launch
        "datareporting.policy.dataSubmissionPolicyBypassNotification": True,
        # Don't report telemetry information
        "toolkit.telemetry.enabled": False,
        # Allow sideloading extensions
        "extensions.autoDisableScopes": 0,
        # Disable what's new page
        "browser.startup.homepage_override.mstone": "ignore",
    }


@REGISTRY.register("firefox")
class FirefoxLauncher(MozRunnerLauncher):
    profile_class = FirefoxRegressionProfile

    def _install(self, dest):
        super(FirefoxLauncher, self)._install(dest)
        self._disableUpdateByPolicy()

        if self._codesign_invalid_on_macOS_13:
            LOG.warning(f"codesign verification failed for {self.appdir}, re-signing...")
            self._codesign_sign(self.appdir)


class ThunderbirdRegressionProfile(ThunderbirdProfile):
    """
    Specialized Profile subclass for Thunderbird
    """

    preferences = {
        # Don't automatically update the application
        "app.update.enabled": False,
        "app.update.auto": False,
    }


@REGISTRY.register("thunderbird")
class ThunderbirdLauncher(MozRunnerLauncher):
    profile_class = ThunderbirdRegressionProfile

    def _install(self, dest):
        super(ThunderbirdLauncher, self)._install(dest)
        self._disableUpdateByPolicy()

        if self._codesign_invalid_on_macOS_13:
            LOG.warning(f"codesign verification failed for {self.appdir}, re-signing...")
            self._codesign_sign(self.appdir)


class AndroidLauncher(Launcher):
    app_info = None
    adb = None
    package_name = None
    profile_class = FirefoxRegressionProfile
    remote_profile = None

    @abstractmethod
    def _get_package_name(self):
        raise NotImplementedError

    @abstractmethod
    def _launch(self):
        raise NotImplementedError

    @classmethod
    def check_is_runnable(cls):
        try:
            devices = ADBHost().devices()
        except ADBError as adb_error:
            raise LauncherNotRunnable(str(adb_error))
        if not devices:
            raise LauncherNotRunnable(
                "No android device connected." " Connect a device and try again."
            )

    def _install(self, dest):
        # get info now, as dest may be removed
        self.app_info = safe_get_version(binary=dest)
        self.package_name = self.app_info.get("package_name", self._get_package_name())
        self.adb = ADBDeviceFactory()
        try:
            self.adb.uninstall_app(self.package_name)
        except ADBError as msg:
            LOG.warning(
                "Failed to uninstall %s (%s)\nThis is normal if it is the"
                " first time the application is installed." % (self.package_name, msg)
            )
        self.adb.run_as_package = self.adb.install_app(dest)

    def _start(
        self,
        profile=None,
        addons=(),
        cmdargs=(),
        preferences=None,
        adb_profile_dir=None,
    ):
        # for now we don't handle addons on the profile for fennec
        profile = self._create_profile(profile=profile, preferences=preferences)
        # send the profile on the device
        if not adb_profile_dir:
            adb_profile_dir = self.adb.test_root
        self.remote_profile = "/".join([adb_profile_dir, os.path.basename(profile.profile)])
        if self.adb.exists(self.remote_profile):
            self.adb.rm(self.remote_profile, recursive=True)
        LOG.debug("Pushing profile to device (%s -> %s)" % (profile.profile, self.remote_profile))
        self.adb.push(profile.profile, self.remote_profile)
        if cmdargs and len(cmdargs) == 1 and not cmdargs[0].startswith("-"):
            url = cmdargs[0]
        else:
            url = None
        if isinstance(self, (FenixLauncher, FennecLauncher, FocusLauncher)):
            self._launch(url=url)
        else:
            self._launch()

    def _wait(self):
        while self.adb.process_exist(self.package_name):
            time.sleep(0.1)

    def _stop(self):
        self.adb.stop_application(self.package_name)
        if self.adb.exists(self.remote_profile):
            self.adb.rm(self.remote_profile, recursive=True)

    def launch_browser(
        self,
        app_name,
        activity,
        intent="android.intent.action.VIEW",
        moz_env=None,
        url=None,
        wait=True,
        fail_if_running=True,
        timeout=None,
    ):
        extras = {}
        extras["args"] = f"-profile {self.remote_profile}"

        self.adb.launch_application(
            app_name,
            activity,
            intent,
            url=url,
            extras=extras,
            wait=wait,
            fail_if_running=fail_if_running,
            timeout=timeout,
        )

    def get_app_info(self):
        return self.app_info


@REGISTRY.register("fennec")
class FennecLauncher(AndroidLauncher):
    def _get_package_name(self):
        return "org.mozilla.fennec"

    def _launch(self, url=None):
        LOG.debug("Launching fennec")
        self.launch_browser(self.package_name, "org.mozilla.gecko.BrowserApp", url=url)


@REGISTRY.register("fenix")
class FenixLauncher(AndroidLauncher):
    def _get_package_name(self):
        return "org.mozilla.fenix"

    def _launch(self, url=None):
        LOG.debug("Launching fenix")
        self.launch_browser(self.package_name, ".IntentReceiverActivity", url=url)


@REGISTRY.register("focus")
class FocusLauncher(AndroidLauncher):
    def _get_package_name(self):
        return "org.mozilla.focus.nightly"

    def _launch(self, url=None):
        LOG.debug("Launching focus")
        self.launch_browser(
            self.package_name,
            "org.mozilla.focus.activity.IntentReceiverActivity",
            url=url,
        )


@REGISTRY.register("gve")
class GeckoViewExampleLauncher(AndroidLauncher):
    def _get_package_name(self):
        return "org.mozilla.geckoview_example"

    def _launch(self):
        LOG.debug("Launching geckoview_example")
        self.adb.launch_activity(
            self.package_name,
            activity_name="GeckoViewActivity",
            extra_args=["-profile", self.remote_profile],
            e10s=True,
        )


@REGISTRY.register("jsshell")
class JsShellLauncher(Launcher):
    temp_dir = None

    def _install(self, dest):
        self.tempdir = safe_mkdtemp()
        try:
            with zipfile.ZipFile(dest, "r") as z:
                z.extractall(self.tempdir)
            self.binary = os.path.join(self.tempdir, "js" if mozinfo.os != "win" else "js.exe")
            # set the file executable
            os.chmod(self.binary, os.stat(self.binary).st_mode | stat.S_IEXEC)
        except Exception:
            remove(self.tempdir)
            raise

    def _start(self, **kwargs):
        LOG.info("Launching %s" % self.binary)
        res = call([self.binary], cwd=self.tempdir)
        if res != 0:
            LOG.warning("jsshell exited with code %d." % res)

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
                remove(self.tempdir)


# Should this be part of mozrunner ?
class SnapRunner(GeckoRuntimeRunner):
    _allow_sudo = False
    _snap_pkg = None

    def __init__(self, binary, cmdargs, allow_sudo=False, snap_pkg=None, **runner_args):
        self._allow_sudo = allow_sudo
        self._snap_pkg = snap_pkg
        super().__init__(binary, cmdargs, **runner_args)

    @property
    def command(self):
        """
        Rewrite the command for performing the actual execution with
        "snap run PKG", keeping everything else
        """
        self._command = FirefoxSnapLauncher._get_snap_command(
            self._allow_sudo, "run", [self._snap_pkg] + super().command[1:]
        )
        return self._command


@REGISTRY.register("firefox-snap")
class FirefoxSnapLauncher(MozRunnerLauncher):
    profile_class = FirefoxRegressionProfile
    instanceKey = None
    snap_pkg = None
    binary = None
    allow_sudo = False
    disable_snap_connect = False
    runner = None

    def __init__(self, dest, **kwargs):
        self.allow_sudo = kwargs["launcher_args"]["allow_sudo"]
        self.disable_snap_connect = kwargs["launcher_args"]["disable_snap_connect"]

        if not self.allow_sudo:
            LOG.info(
                "Working with snap requires several 'sudo snap' commands. "
                "Not allowing the use of sudo will trigger many password confirmation dialog boxes."
            )
        else:
            LOG.info("Usage of sudo enabled, you should be prompted for your password once.")

        super().__init__(dest)

    def get_snap_command(self, action, extra):
        return FirefoxSnapLauncher._get_snap_command(self.allow_sudo, action, extra)

    def _get_snap_command(allow_sudo, action, extra):
        if action not in ("connect", "install", "run", "refresh", "remove"):
            raise LauncherError(f"Snap operation {action} unsupported")

        cmd = []
        if allow_sudo and action in ("connect", "install", "refresh", "remove"):
            cmd += ["sudo"]

        cmd += ["snap", action]
        cmd += extra

        return cmd

    def _install(self, dest):
        # From https://snapcraft.io/docs/parallel-installs#heading--naming
        #  - The instance key needs to be manually appended to the snap name,
        #    and takes the following format: <snap>_<instance-key>
        #  - The instance key must match the following regular expression:
        #    ^[a-z0-9]{1,10}$.
        self.instanceKey = hashlib.sha1(os.path.basename(dest).encode("utf8")).hexdigest()[0:9]
        self.snap_pkg = "firefox_{}".format(self.instanceKey)
        self.binary = "/snap/{}/current/usr/lib/firefox/firefox".format(self.snap_pkg)

        subprocess.run(
            self.get_snap_command(
                "install", ["--name", self.snap_pkg, "--dangerous", "{}".format(dest)]
            ),
            check=True,
        )
        self._fix_connections()

        self.binarydir = os.path.dirname(self.binary)
        self.appdir = os.path.normpath(os.path.join(self.binarydir, "..", ".."))

        LOG.debug(f"snap package: {self.snap_pkg} {self.binary}")

        # On Snap updates are already disabled

    def _fix_connections(self):
        if self.disable_snap_connect:
            return

        existing = {}
        for line in subprocess.getoutput("snap connections {}".format(self.snap_pkg)).splitlines()[
            1:
        ]:
            interface, plug, slot, _ = line.split()
            existing[plug] = slot

        for line in subprocess.getoutput("snap connections firefox").splitlines()[1:]:
            interface, plug, slot, _ = line.split()
            ex_plug = plug.replace("firefox:", "{}:".format(self.snap_pkg))
            ex_slot = slot.replace("firefox:", "{}:".format(self.snap_pkg))
            if existing[ex_plug] == "-":
                if ex_plug != "-" and ex_slot != "-":
                    cmd = self.get_snap_command(
                        "connect", ["{}".format(ex_plug), "{}".format(ex_slot)]
                    )
                    LOG.debug(f"snap connect: {cmd}")
                    subprocess.run(cmd, check=True)

    def _create_profile(self, profile=None, addons=(), preferences=None):
        """
        Let's create a profile as usual, but rewrite its path to be in Snap's
        dir because it looks like MozProfile class will consider a profile=xxx
        to be a pre-existing one
        """
        real_profile = super()._create_profile(profile, addons, preferences)
        snap_profile_dir = os.path.abspath(
            os.path.expanduser("~/snap/{}/common/.mozilla/firefox/".format(self.snap_pkg))
        )
        if not os.path.exists(snap_profile_dir):
            os.makedirs(snap_profile_dir)
        profile_dir_name = os.path.basename(real_profile.profile)
        snap_profile = os.path.join(snap_profile_dir, profile_dir_name)
        move(real_profile.profile, snap_profile_dir)
        real_profile.profile = snap_profile
        return real_profile

    def _start(
        self,
        profile=None,
        addons=(),
        cmdargs=(),
        preferences=None,
        adb_profile_dir=None,
        allow_sudo=False,
        disable_snap_connect=False,
    ):
        profile = self._create_profile(profile=profile, addons=addons, preferences=preferences)

        LOG.info("Launching %s [%s]" % (self.binary, self.allow_sudo))
        self.runner = SnapRunner(
            binary=self.binary,
            cmdargs=cmdargs,
            profile=profile,
            allow_sudo=self.allow_sudo,
            snap_pkg=self.snap_pkg,
        )
        self.runner.start()

    def _wait(self):
        self.runner.wait()

    def _stop(self):
        self.runner.stop()
        # release the runner since it holds a profile reference
        del self.runner

    def cleanup(self):
        try:
            Launcher.cleanup(self)
        finally:
            subprocess.run(self.get_snap_command("remove", [self.snap_pkg]))

    def get_app_info(self):
        return safe_get_version(binary=self.binary)
