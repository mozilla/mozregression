from __future__ import absolute_import

import os
import sys
import tempfile
import unittest
from subprocess import CalledProcessError

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


class TestMozRunnerLauncher__codesign(unittest.TestCase):
    """Test codesign functionality."""

    @patch("mozregression.launchers.mozinfo")
    @patch("mozregression.launchers.mozinstall")
    def test__codesign_verify_raises_if_not_mac(self, mozinstall, mozinfo):
        mozinstall.get_binary.return_value = "/binary"
        mozinfo.os = "notmac"
        launcher = launchers.MozRunnerLauncher("/binary")
        with pytest.raises(Exception) as e:
            launcher._codesign_verify("/")
        assert str(e.value) == "_codesign_verify should only be called on macOS."

    @patch("mozregression.launchers.mozinfo")
    @patch("mozregression.launchers.mozinstall")
    @patch("mozregression.launchers.check_output")
    def test__codesign_verify_returns_correct_code(self, check_output, mozinstall, mozinfo):
        mozinstall.get_binary.return_value = "/binary"
        mozinfo.os = "mac"
        launcher = launchers.MozRunnerLauncher("/binary")

        # There is no output when verification is successful.
        check_output.return_value = ""
        result = launcher._codesign_verify("/")
        assert result == launchers.CodesignResult.PASS

        # There is an output and error code when unsuccessful.
        check_output.side_effect = CalledProcessError(
            1, [], output=b"\ncode object is not signed at all\n"
        )

        result = launcher._codesign_verify("/")
        assert result is launchers.CodesignResult.UNSIGNED

        check_output.side_effect = CalledProcessError(
            1, [], output=b"\na sealed resource is missing or invalid\n"
        )

        result = launcher._codesign_verify("/")
        assert result is launchers.CodesignResult.INVALID

        check_output.side_effect = CalledProcessError(2, [], output=b"\nunknown error occurred\n")

        result = launcher._codesign_verify("/")
        assert result is launchers.CodesignResult.OTHER

    @patch("mozregression.launchers.mozinfo")
    @patch("mozregression.launchers.mozinstall")
    def test__codesign_sign_raises_if_not_mac(self, mozinstall, mozinfo):
        mozinstall.get_binary.return_value = "/binary"
        mozinfo.os = "notmac"
        with pytest.raises(Exception) as e:
            launchers.MozRunnerLauncher._codesign_sign("/")
        assert str(e.value) == "_codesign_sign should only be called on macOS."

    @patch("mozregression.launchers.call")
    @patch("mozregression.launchers.mozinfo")
    @patch("mozregression.launchers.mozinstall")
    def test__codesign_sign(self, mozinstall, mozinfo, call):
        mozinstall.get_binary.return_value = "/binary"
        mozinfo.os = "mac"
        launchers.MozRunnerLauncher._codesign_sign("/")
        call.assert_called_with(["codesign", "--force", "--deep", "--sign", "-", "/"])
        call.assert_called_once()

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="os.path.normpath behaviour on Windows interferes with this test",
    )
    @patch("mozregression.launchers.mozinfo")
    @patch("mozregression.launchers.mozinstall")
    def test__codesign_assert_resigned_if_unsigned(self, mozinstall, mozinfo):
        mozinstall.get_binary.return_value = "/binary"
        mozinfo.os = "mac"
        with patch.object(
            launchers.MozRunnerLauncher,
            "_codesign_verify",
            return_value=launchers.CodesignResult.UNSIGNED,
        ):
            with patch.object(launchers.MozRunnerLauncher, "_codesign_sign") as _codesign_sign:
                launchers.MozRunnerLauncher("/binary")
                _codesign_sign.assert_called_with("/")

    @patch("mozregression.launchers.mozinfo")
    @patch("mozregression.launchers.mozinstall")
    def test__codesign_assert_no_calls_if_not_on_mac(self, mozinstall, mozinfo):
        mozinstall.get_binary.return_value = "/binary"
        mozinfo.os = "notmac"
        with patch.object(launchers.MozRunnerLauncher, "_codesign_verify") as _codesign_verify:
            with patch.object(launchers.MozRunnerLauncher, "_codesign_sign") as _codesign_sign:
                launchers.MozRunnerLauncher("/binary")
                _codesign_sign.assert_not_called()
                _codesign_verify.assert_not_called()

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="os.path.normpath behaviour on Windows interferes with this test",
    )
    @patch("mozregression.launchers.mozinfo")
    @patch("mozregression.launchers.mozinstall")
    def test__codesign_assert_not_resigned_if_not_unsigned(self, mozinstall, mozinfo):
        mozinstall.get_binary.return_value = "/binary"
        mozinfo.os = "mac"
        with patch.object(
            launchers.MozRunnerLauncher,
            "_codesign_verify",
            return_value=launchers.CodesignResult.INVALID,
        ) as _codesign_verify:
            with patch.object(launchers.MozRunnerLauncher, "_codesign_sign") as _codesign_sign:
                launchers.MozRunnerLauncher("/binary")
                _codesign_verify.assert_called_with("/")
                _codesign_sign.assert_not_called()


@pytest.mark.parametrize(
    "verify_return_value,sign_call_count",
    [
        (launchers.CodesignResult.PASS, 0),
        (launchers.CodesignResult.UNSIGNED, 1),
        (launchers.CodesignResult.INVALID, 1),
        (launchers.CodesignResult.OTHER, 0),
    ],
)
@patch("mozregression.launchers.FirefoxLauncher._codesign_sign")
@patch("mozregression.launchers.FirefoxLauncher._codesign_verify")
def test_firefox_install(
    _mock_codesign_verify, _mock_codesign_sign, verify_return_value, sign_call_count, mocker
):
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

    if mozinfo.isMac:
        _mock_codesign_verify.return_value = verify_return_value

    with launchers.FirefoxLauncher(installer) as fx:
        assert os.path.isdir(fx.tempdir)
        assert os.path.basename(fx.binary) == binary_name
        installdir = os.path.dirname(fx.binary)
        if mozinfo.isMac:
            installdir = os.path.normpath(os.path.join(installdir, "..", "Resources"))
        assert os.path.exists(os.path.join(installdir, "distribution", "policies.json"))
    assert not os.path.isdir(fx.tempdir)

    if not mozinfo.isMac:
        assert _mock_codesign_verify.call_count == 0
        assert _mock_codesign_sign.call_count == 0
    else:
        assert _mock_codesign_sign.call_count == sign_call_count


@pytest.mark.parametrize(
    "launcher_class,package_name,intended_activity",
    [
        (launchers.FennecLauncher, "org.mozilla.fennec", "org.mozilla.gecko.BrowserApp"),
        (launchers.FenixLauncher, "org.mozilla.fenix", ".IntentReceiverActivity"),
        (
            launchers.FocusLauncher,
            "org.mozilla.focus.nightly",
            "org.mozilla.focus.activity.IntentReceiverActivity",
        ),
    ],
)
class TestExtendedAndroidLauncher:
    test_root = "/sdcard/tmp"

    def setup_method(self):
        self.profile = Profile()
        self.remote_profile_path = self.test_root + "/" + os.path.basename(self.profile.profile)

    def teardown_method(self):
        self.profile.cleanup()

    @patch("mozregression.launchers.mozversion.get_version")
    @patch("mozregression.launchers.ADBDeviceFactory")
    def create_launcher(self, ADBDeviceFactory, get_version, launcher_class=None, **kwargs):
        self.adb = Mock(test_root=self.test_root)
        if kwargs.get("uninstall_error"):
            self.adb.uninstall_app.side_effect = launchers.ADBError
        ADBDeviceFactory.return_value = self.adb
        get_version.return_value = kwargs.get("version_value", {})
        return launcher_class("/binary")

    def test_install(self, launcher_class, package_name, intended_activity):
        self.create_launcher(launcher_class=launcher_class)
        self.adb.uninstall_app.assert_called_with(package_name)
        self.adb.install_app.assert_called_with("/binary")

    def test_start_stop(self, launcher_class, package_name, intended_activity, **kwargs):
        with patch(
            f"mozregression.launchers.{launcher_class.__name__}._create_profile"
        ) as _create_profile:
            # Force use of existing profile
            _create_profile.return_value = self.profile
            launcher = self.create_launcher(launcher_class=launcher_class)
            launcher.start(profile="my_profile")
            self.adb.exists.assert_called_once_with(self.remote_profile_path)
            self.adb.rm.assert_called_once_with(self.remote_profile_path, recursive=True)
            self.adb.push.assert_called_once_with(self.profile.profile, self.remote_profile_path)
            self.adb.launch_application.assert_called_once_with(
                package_name,
                intended_activity,
                "android.intent.action.VIEW",
                url=None,
                extras={"args": f"-profile {self.remote_profile_path}"},
                wait=True,
                fail_if_running=True,
                timeout=None,
            )
            # ensure get_app_info returns something
            assert launcher.get_app_info() is not None
            launcher.stop()
            self.adb.stop_application.assert_called_once_with(package_name)

    def test_adb_calls_with_custom_package_name(
        self, launcher_class, package_name, intended_activity
    ):
        with patch(
            f"mozregression.launchers.{launcher_class.__name__}._create_profile"
        ) as _create_profile:
            # Force use of existing profile
            _create_profile.return_value = self.profile
            pkg_name = "org.mozilla.custom"
            launcher = self.create_launcher(
                version_value={"package_name": pkg_name}, launcher_class=launcher_class
            )
            self.adb.uninstall_app.assert_called_once_with(pkg_name)
            launcher.start(profile="my_profile")
            self.adb.launch_application.assert_called_once_with(
                pkg_name,
                intended_activity,
                "android.intent.action.VIEW",
                url=None,
                extras={"args": f"-profile {self.remote_profile_path}"},
                wait=True,
                fail_if_running=True,
                timeout=None,
            )
            launcher.stop()
            self.adb.stop_application.assert_called_once_with(pkg_name)

    @patch("mozregression.launchers.LOG")
    def test_adb_first_uninstall_fail(self, log, launcher_class, package_name, intended_activity):
        self.create_launcher(uninstall_error=True, launcher_class=launcher_class)
        log.warning.assert_called_once_with(ANY)
        self.adb.install_app.assert_called_once_with(ANY)

    @patch("mozregression.launchers.ADBHost")
    def test_check_is_runnable(self, ADBHost, launcher_class, package_name, intended_activity):
        devices = Mock(return_value=True)
        ADBHost.return_value = Mock(devices=devices)
        # this won't raise errors
        launcher_class.check_is_runnable()

        # exception raised if there is no device
        devices.return_value = False
        with pytest.raises(LauncherNotRunnable):
            launcher_class.check_is_runnable()

        # or if ADBHost().devices() raise an unexpected IOError
        devices.side_effect = ADBError()
        with pytest.raises(LauncherNotRunnable):
            launcher_class.check_is_runnable()

    @patch("time.sleep")
    def test_wait(self, sleep, launcher_class, package_name, intended_activity):
        with patch(
            f"mozregression.launchers.{launcher_class.__name__}._create_profile"
        ) as _create_profile:
            # Force use of existing profile
            _create_profile.return_value = self.profile
        launcher = self.create_launcher(launcher_class=launcher_class)

        passed = []

        def proc_exists(name):
            # return True one time, then False
            result = not bool(passed)
            passed.append(1)
            return result

        self.adb.process_exist = Mock(side_effect=proc_exists)
        launcher.start()
        launcher.wait()
        self.adb.process_exist.assert_called_with(package_name)

    def test_start_with_url(self, launcher_class, package_name, intended_activity, **kwargs):
        with patch(
            f"mozregression.launchers.{launcher_class.__name__}._create_profile"
        ) as _create_profile:
            # Force use of existing profile
            _create_profile.return_value = self.profile
            launcher = self.create_launcher(launcher_class=launcher_class)
            launcher.start(profile="my_profile", cmdargs=("https://example.org/",))
            self.adb.launch_application.assert_called_once_with(
                package_name,
                intended_activity,
                "android.intent.action.VIEW",
                url="https://example.org/",
                extras={"args": f"-profile {self.remote_profile_path}"},
                wait=True,
                fail_if_running=True,
                timeout=None,
            )


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
