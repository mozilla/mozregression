from __future__ import absolute_import

import datetime
import unittest

import pytest
from mock import Mock, patch

from mozregression import build_info, errors, test_runner


def mockinfo(**kwargs):
    return Mock(spec=build_info.BuildInfo, **kwargs)


class Launcher(object):
    # mock does not play well with context manager, so this is a stub
    def __init__(self, launcher):
        self.launcher = launcher

    def __enter__(self):
        return self.launcher

    def __exit__(self, *exc):
        pass


class TestManualTestRunner(unittest.TestCase):
    def setUp(self):
        self.runner = test_runner.ManualTestRunner()

    @patch("mozregression.test_runner.mozlauncher")
    def test_nightly_create_launcher(self, create_launcher):
        launcher = Mock()
        create_launcher.return_value = launcher
        info = mockinfo(build_type="nightly", app_name="firefox", build_file="/path/to")
        result_launcher = test_runner.create_launcher(info)
        create_launcher.assert_called_with(info)

        self.assertEqual(result_launcher, launcher)

    @patch("mozregression.test_runner.mozlauncher")
    @patch("mozregression.test_runner.LOG")
    def test_nightly_create_launcher_buildid(self, log, mozlauncher):
        launcher = Mock()
        mozlauncher.return_value = launcher
        info = mockinfo(
            build_type="nightly",
            app_name="firefox",
            build_file="/path/to",
            build_date=datetime.datetime(2015, 11, 6, 5, 4, 3),
            repo_name="mozilla-central",
        )
        result_launcher = test_runner.create_launcher(info)
        mozlauncher.assert_called_with(info)
        log.info.assert_called_with("Running mozilla-central build for buildid 20151106050403")

        self.assertEqual(result_launcher, launcher)

    @patch("mozregression.download_manager.DownloadManager.download")
    @patch("mozregression.test_runner.mozlauncher")
    def test_inbound_create_launcher(self, mozlauncher, download):
        launcher = Mock()
        mozlauncher.return_value = launcher
        info = mockinfo(build_type="inbound", app_name="firefox", build_file="/path/to")
        result_launcher = test_runner.create_launcher(info)
        mozlauncher.assert_called_with(info)
        self.assertEqual(result_launcher, launcher)

    @patch("mozregression.test_runner.input")
    def test_get_verdict(self, input):
        input.return_value = "g"
        verdict = self.runner.get_verdict(mockinfo(build_type="inbound"), False)
        self.assertEqual(verdict, "g")

        output = input.call_args[0][0]
        # bad is proposed
        self.assertIn("bad", output)
        # back is not
        self.assertNotIn("back", output)

    @patch("mozregression.test_runner.input")
    def test_get_verdict_allow_back(self, input):
        input.return_value = "back"
        verdict = self.runner.get_verdict(mockinfo(build_type="inbound"), True)
        output = input.call_args[0][0]
        # back is now proposed
        self.assertIn("back", output)
        self.assertEqual(verdict, "back")

    @patch("mozregression.test_runner.create_launcher")
    @patch("mozregression.test_runner.ManualTestRunner.get_verdict")
    def test_evaluate(self, get_verdict, create_launcher):
        get_verdict.return_value = "g"
        launcher = Mock()
        create_launcher.return_value = Launcher(launcher)
        build_infos = mockinfo()
        result = self.runner.evaluate(build_infos)

        create_launcher.assert_called_with(build_infos)
        launcher.get_app_info.assert_called_with()
        launcher.start.assert_called_with()
        get_verdict.assert_called_with(build_infos, False)
        launcher.stop.assert_called_with()
        self.assertEqual(result[0], "g")

    @patch("mozregression.test_runner.create_launcher")
    @patch("mozregression.test_runner.ManualTestRunner.get_verdict")
    def test_evaluate_with_launcher_error_on_stop(self, get_verdict, create_launcher):
        get_verdict.return_value = "g"
        launcher = Mock(stop=Mock(side_effect=errors.LauncherError))
        create_launcher.return_value = Launcher(launcher)
        build_infos = mockinfo()
        result = self.runner.evaluate(build_infos)

        # the LauncherError is silently ignore here
        launcher.stop.assert_called_with()
        self.assertEqual(result[0], "g")

    @patch("mozregression.test_runner.create_launcher")
    def test_run_once(self, create_launcher):
        launcher = Mock(wait=Mock(return_value=0))
        create_launcher.return_value = Launcher(launcher)
        build_infos = mockinfo()
        self.assertEqual(self.runner.run_once(build_infos), 0)
        create_launcher.assert_called_with(build_infos)
        launcher.get_app_info.assert_called_with()
        launcher.start.assert_called_with()
        launcher.wait.assert_called_with()

    @patch("mozregression.test_runner.create_launcher")
    def test_run_once_ctrlc(self, create_launcher):
        launcher = Mock(wait=Mock(side_effect=KeyboardInterrupt))
        create_launcher.return_value = Launcher(launcher)
        build_infos = mockinfo()
        with self.assertRaises(KeyboardInterrupt):
            self.runner.run_once(build_infos)
        create_launcher.assert_called_with(build_infos)
        launcher.get_app_info.assert_called_with()
        launcher.start.assert_called_with()
        launcher.wait.assert_called_with()


class TestCommandTestRunner(unittest.TestCase):
    def setUp(self):
        self.runner = test_runner.CommandTestRunner("my command")
        self.launcher = Mock()
        del self.launcher.binary  # block the auto attr binary on the mock

        if not hasattr(self, "assertRaisesRegex"):
            self.assertRaisesRegex = self.assertRaisesRegexp

    def test_create(self):
        self.assertEqual(self.runner.command, "my command")

    @patch("mozregression.test_runner.create_launcher")
    @patch("subprocess.call")
    def evaluate(
        self,
        call,
        create_launcher,
        build_info={},
        retcode=0,
        subprocess_call_effect=None,
    ):
        build_info["app_name"] = "myapp"
        call.return_value = retcode
        if subprocess_call_effect:
            call.side_effect = subprocess_call_effect
        self.subprocess_call = call
        create_launcher.return_value = Launcher(self.launcher)
        return self.runner.evaluate(mockinfo(to_dict=lambda: build_info))[0]

    def test_evaluate_retcode(self):
        self.assertEqual("g", self.evaluate(retcode=0))
        self.assertEqual("b", self.evaluate(retcode=1))

    def test_supbrocess_call(self):
        self.evaluate()
        command = self.subprocess_call.mock_calls[0][1][0]
        kwargs = self.subprocess_call.mock_calls[0][2]
        self.assertEqual(command, ["my", "command"])
        self.assertIn("env", kwargs)

    def test_env_vars(self):
        self.evaluate(build_info={"my": "var", "int": 15})
        expected = {
            "MOZREGRESSION_MY": "var",
            "MOZREGRESSION_INT": "15",
            "MOZREGRESSION_APP_NAME": "myapp",
        }
        passed_env = self.subprocess_call.mock_calls[0][2]["env"]
        self.assertTrue(set(expected).issubset(set(passed_env)))

    def test_command_placeholder_replaced(self):
        self.runner.command = 'run {app_name} "1"'
        self.evaluate()
        command = self.subprocess_call.mock_calls[0][1][0]
        self.assertEqual(command, ["run", "myapp", "1"])

        self.runner.command = "run '{binary}' \"{foo}\""
        self.launcher.binary = "mybinary"
        self.evaluate(build_info={"foo": 12})
        command = self.subprocess_call.mock_calls[0][1][0]
        self.assertEqual(command, ["run", "mybinary", "12"])

    def test_command_placeholder_error(self):
        self.runner.command = 'run {app_nam} "1"'
        self.assertRaisesRegex(errors.TestCommandError, "formatting", self.evaluate)

    def test_command_empty_error(self):
        # in case the command line is empty,
        # subprocess.call will raise IndexError
        self.assertRaisesRegex(
            errors.TestCommandError,
            "Empty",
            self.evaluate,
            subprocess_call_effect=IndexError,
        )

    def test_command_missing_error(self):
        # in case the command is missing or not executable,
        # subprocess.call will raise IOError
        self.assertRaisesRegex(
            errors.TestCommandError,
            "not found",
            self.evaluate,
            subprocess_call_effect=OSError,
        )

    def test_run_once(self):
        self.runner.evaluate = Mock(return_value="g")
        build_info = Mock()
        self.assertEqual(self.runner.run_once(build_info), 0)
        self.runner.evaluate.assert_called_once_with(build_info)


@pytest.mark.parametrize(
    "brange,input,allowed_range,result",
    [  # noqa
        # [0, 1, 2, 3, 4, 5] (6 elements, mid is '3')
        (list(range(6)), ["-2"], "[-2, 1]", 1),
        # [0, 1, 2, 3, 4] (5 elements, mid is '2')
        (list(range(5)), ["1"], "[-1, 1]", 3),
        # user hit something bad, we loop
        (list(range(5)), ["aa", "", "1"], "[-1, 1]", 3),
        # small range, no input
        (list(range(3)), Exception("input called, it should not happen"), None, 1),
    ],
)
def test_index_to_try_after_skip(mocker, range_creator, brange, input, allowed_range, result):
    build_range = range_creator.create(brange)
    mocked_input = mocker.patch("mozregression.test_runner.input")
    mocked_input.side_effect = input
    output = []
    mocked_stdout = mocker.patch("sys.stdout")
    mocked_stdout.write = output.append

    runner = test_runner.ManualTestRunner()
    assert runner.index_to_try_after_skip(build_range) == result
    if allowed_range is not None:
        assert ("You can choose a build index between %s:" % allowed_range) in [
            o.strip() for o in output
        ]
