from __future__ import absolute_import

import os
import sys
import tempfile
import unittest

import mozfile
import mozinfo
import mozversion
import pytest
from mock import ANY, Mock, patch
from mozdevice import ADBError
from mozprofile import Profile

from mozregression import launchers
from mozregression.errors import LauncherError, LauncherNotRunnable


class MyLauncher(launchers.Launcher):
    installed = None
    started = False
    stopped = False

    def _install(self, dest):
        self.installed = dest

    def _start(self):
        self.started = True

    def _stop(self):
        self.stopped = True

    def _wait(self):
        return 0


class TestLauncher(unittest.TestCase):
    def test_start_stop(self):
        launcher = MyLauncher("/foo/persist.zip")
        self.assertFalse(launcher.started)
        launcher.start()
        # now it has been started
        self.assertTrue(launcher.started)
        # restarting won't do anything because it was not stopped
        launcher.started = False
        launcher.start()
        self.assertFalse(launcher.started)
        # stop it, then start it again, this time _start is called again
        launcher.stop()
        launcher.start()
        self.assertTrue(launcher.started)

    def test_wait(self):
        launcher = MyLauncher("/foo/persist.zip")
        self.assertFalse(launcher.started)
        launcher.start()
        # now it has been started
        self.assertTrue(launcher.started)

        self.assertEqual(launcher.wait(), 0)
        self.assertTrue(launcher.stopped)

    def test_install_fail(self):
        class FailingLauncher(MyLauncher):
            def _install(self, dest):
                raise Exception()

        with self.assertRaises(LauncherError):
            FailingLauncher("/foo/persist.zip")

    def test_start_fail(self):
        launcher = MyLauncher("/foo/persist.zip")
        launcher._start = Mock(side_effect=Exception)

        with self.assertRaises(LauncherError):
            launcher.start()

    def test_stop_fail(self):
        launcher = MyLauncher("/foo/persist.zip")
        launcher._stop = Mock(side_effect=Exception)

        launcher.start()
        with self.assertRaises(LauncherError):
            launcher.stop()


class TestMozRunnerLauncher(unittest.TestCase):
    @patch("mozregression.launchers.mozinstall")
    def setUp(self, mozinstall):
        mozinstall.get_binary.return_value = "/binary"
        self.launcher = launchers.MozRunnerLauncher("/binary")

    # patch profile_class else we will have some temporary dirs not deleted
    @patch(
        "mozregression.launchers.MozRunnerLauncher.\
profile_class",
        spec=Profile,
    )
    def launcher_start(self, profile_class, *args, **kwargs):
        self.profile_class = profile_class
        self.launcher.start(*args, **kwargs)

    def test_installed(self):
        with self.launcher:
            self.assertEqual(self.launcher.binary, "/binary")

    @patch("mozregression.launchers.Runner")
    def test_start_no_args(self, Runner):
        with self.launcher:
            self.launcher_start()
            kwargs = Runner.call_args[1]

            self.assertEqual(kwargs["cmdargs"], ())
            self.assertEqual(kwargs["binary"], "/binary")
            self.assertIsInstance(kwargs["profile"], Profile)
            # runner is started
            self.launcher.runner.start.assert_called_once_with()
            self.launcher.stop()

    @patch("mozregression.launchers.Runner")
    def test_wait(self, Runner):
        runner = Mock(wait=Mock(return_value=0))
        Runner.return_value = runner
        with self.launcher:
            self.launcher_start()
            self.assertEqual(self.launcher.wait(), 0)
            runner.wait.assert_called_once_with()

    @patch("mozregression.launchers.Runner")
    def test_start_with_addons(self, Runner):
        with self.launcher:
            self.launcher_start(addons=["my-addon"], preferences="my-prefs")
            self.profile_class.assert_called_once_with(addons=["my-addon"], preferences="my-prefs")
            # runner is started
            self.launcher.runner.start.assert_called_once_with()
            self.launcher.stop()

    @patch("mozregression.launchers.Runner")
    def test_start_with_profile_and_addons(self, Runner):
        temp_dir_profile = tempfile.mkdtemp()
        self.addCleanup(mozfile.remove, temp_dir_profile)

        with self.launcher:
            self.launcher_start(
                profile=temp_dir_profile, addons=["my-addon"], preferences="my-prefs"
            )
            self.profile_class.clone.assert_called_once_with(
                temp_dir_profile, addons=["my-addon"], preferences="my-prefs"
            )
            # runner is started
            self.launcher.runner.start.assert_called_once_with()
            self.launcher.stop()

    @patch("mozregression.launchers.Runner")
    @patch("mozregression.launchers.mozversion")
    def test_get_app_infos(self, mozversion, Runner):
        mozversion.get_version.return_value = {"some": "infos"}
        with self.launcher:
            self.launcher_start()
            self.assertEqual(self.launcher.get_app_info(), {"some": "infos"})
            mozversion.get_version.assert_called_once_with(binary="/binary")
            self.launcher.stop()

    @patch("mozregression.launchers.Runner")
    @patch("mozversion.get_version")
    def test_get_app_infos_error(self, get_version, Runner):
        get_version.side_effect = mozversion.VersionError("err")
        with self.launcher:
            self.launcher_start()
            self.assertEqual(self.launcher.get_app_info(), {})

    def test_launcher_deleted_whith_statement(self):
        tempdir = self.launcher.tempdir
        self.assertTrue(os.path.isdir(tempdir))
        with self.launcher:
            pass
        self.assertFalse(os.path.isdir(tempdir))


@pytest.mark.skipif(sys.platform == "darwin", reason="fails on macosx")
def test_firefox_install(mocker):
    install_ext, binary_name = (
        ("zip", "firefox.exe")
        if mozinfo.isWin
        else ("tar.bz2", "firefox")
        if mozinfo.isLinux
        else ("dmg", "firefox")  # if mozinfo.ismac
    )

    installer_file = "firefox.{}".format(install_ext)

    installer = os.path.abspath(os.path.join("tests", "unit", "installer_stubs", installer_file))
    assert os.path.isfile(installer)
    with launchers.FirefoxLauncher(installer) as fx:
        assert os.path.isdir(fx.tempdir)
        assert os.path.basename(fx.binary) == binary_name
        installdir = os.path.dirname(fx.binary)
        if mozinfo.isMac:
            installdir = os.path.normpath(os.path.join(installdir, "..", "Resources"))
        assert os.path.exists(os.path.join(installdir, "distribution", "policies.json"))
    assert not os.path.isdir(fx.tempdir)


class TestFennecLauncher(unittest.TestCase):

    test_root = "/sdcard/tmp"

    def setUp(self):
        self.profile = Profile()
        self.addCleanup(self.profile.cleanup)
        self.remote_profile_path = self.test_root + "/" + os.path.basename(self.profile.profile)

    @patch("mozregression.launchers.mozversion.get_version")
    @patch("mozregression.launchers.ADBDeviceFactory")
    def create_launcher(self, ADBDeviceFactory, get_version, **kwargs):
        self.adb = Mock(test_root=self.test_root)
        if kwargs.get("uninstall_error"):
            self.adb.uninstall_app.side_effect = launchers.ADBError
        ADBDeviceFactory.return_value = self.adb
        get_version.return_value = kwargs.get("version_value", {})
        return launchers.FennecLauncher("/binary")

    def test_install(self):
        self.create_launcher()
        self.adb.uninstall_app.assert_called_with("org.mozilla.fennec")
        self.adb.install_app.assert_called_with("/binary")

    @patch("mozregression.launchers.FennecLauncher._create_profile")
    def test_start_stop(self, _create_profile):
        # Force use of existing profile
        _create_profile.return_value = self.profile
        launcher = self.create_launcher()
        launcher.start(profile="my_profile")
        self.adb.exists.assert_called_once_with(self.remote_profile_path)
        self.adb.rm.assert_called_once_with(self.remote_profile_path, recursive=True)
        self.adb.push.assert_called_once_with(self.profile.profile, self.remote_profile_path)
        self.adb.launch_fennec.assert_called_once_with(
            "org.mozilla.fennec", extra_args=["-profile", self.remote_profile_path]
        )
        # ensure get_app_info returns something
        self.assertIsNotNone(launcher.get_app_info())
        launcher.stop()
        self.adb.stop_application.assert_called_once_with("org.mozilla.fennec")

    @patch("mozregression.launchers.FennecLauncher._create_profile")
    def test_adb_calls_with_custom_package_name(self, _create_profile):
        # Force use of existing profile
        _create_profile.return_value = self.profile
        pkg_name = "org.mozilla.custom"
        launcher = self.create_launcher(version_value={"package_name": pkg_name})
        self.adb.uninstall_app.assert_called_once_with(pkg_name)
        launcher.start(profile="my_profile")
        self.adb.launch_fennec.assert_called_once_with(
            pkg_name, extra_args=["-profile", self.remote_profile_path]
        )
        launcher.stop()
        self.adb.stop_application.assert_called_once_with(pkg_name)

    @patch("mozregression.launchers.LOG")
    def test_adb_first_uninstall_fail(self, log):
        self.create_launcher(uninstall_error=True)
        log.warning.assert_called_once_with(ANY)
        self.adb.install_app.assert_called_once_with(ANY)

    @patch("mozregression.launchers.ADBHost")
    def test_check_is_runnable(self, ADBHost):
        devices = Mock(return_value=True)
        ADBHost.return_value = Mock(devices=devices)
        # this won't raise errors
        launchers.FennecLauncher.check_is_runnable()

        # exception raised if there is no device
        devices.return_value = False
        self.assertRaises(LauncherNotRunnable, launchers.FennecLauncher.check_is_runnable)

        # or if ADBHost().devices() raise an unexpected IOError
        devices.side_effect = ADBError()
        self.assertRaises(LauncherNotRunnable, launchers.FennecLauncher.check_is_runnable)

    @patch("time.sleep")
    @patch("mozregression.launchers.FennecLauncher._create_profile")
    def test_wait(self, _create_profile, sleep):
        # Force use of existing profile
        _create_profile.return_value = self.profile
        launcher = self.create_launcher()

        passed = []

        def proc_exists(name):
            # return True one time, then False
            result = not bool(passed)
            passed.append(1)
            return result

        self.adb.process_exist = Mock(side_effect=proc_exists)
        launcher.start()
        launcher.wait()
        self.adb.process_exist.assert_called_with("org.mozilla.fennec")


class Zipfile(object):
    def __init__(self, *a):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def extractall(self, dirname):
        fname = "js" if launchers.mozinfo.os != "win" else "js.exe"
        with open(os.path.join(dirname, fname), "w") as f:
            f.write("1")


@pytest.mark.parametrize("mos,binary_name", [("win", "js.exe"), ("linux", "js"), ("mac", "js")])
def test_jsshell_install(mocker, mos, binary_name):
    zipfile = mocker.patch("mozregression.launchers.zipfile")
    zipfile.ZipFile = Zipfile

    mocker.patch("mozregression.launchers.mozinfo").os = mos

    with launchers.JsShellLauncher("/path/to") as js:
        assert os.path.isdir(js.tempdir)
        assert os.path.basename(js.binary) == binary_name
    assert not os.path.isdir(js.tempdir)


def test_jsshell_install_except(mocker):
    mocker.patch("mozregression.launchers.zipfile").ZipFile.side_effect = Exception

    with pytest.raises(Exception):
        launchers.JsShellLauncher("/path/to")


@pytest.mark.parametrize("return_code", [0, 1])
def test_jsshell_start(mocker, return_code):
    zipfile = mocker.patch("mozregression.launchers.zipfile")
    zipfile.ZipFile = Zipfile

    call = mocker.patch("mozregression.launchers.call")
    call.return_code = return_code

    logger = Mock()

    with launchers.JsShellLauncher("/path/to") as js:
        js._logger = logger
        js.start()
        assert js.get_app_info() == {}

    call.assert_called_once_with([js.binary], cwd=js.tempdir)
    logger.warning.calls == 0 if return_code else 1
