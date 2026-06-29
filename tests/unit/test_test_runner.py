from __future__ import absolute_import

import datetime
import sys
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

    @unittest.skipIf(sys.platform == "win32", "args is a string on Windows")
    def test_subprocess_call(self):
        self.evaluate()
        command = self.subprocess_call.mock_calls[0][1][0]
        kwargs = self.subprocess_call.mock_calls[0][2]
        self.assertEqual(command, ["my", "command"])
        self.assertIn("env", kwargs)

    @unittest.skipUnless(sys.platform == "win32", "requires Windows")
    def test_subprocess_call_windows(self):
        self.evaluate()
        command = self.subprocess_call.mock_calls[0][1][0]
        kwargs = self.subprocess_call.mock_calls[0][2]
        self.assertEqual(command, "my command")
        self.assertIn("env", kwargs)

    @unittest.skipUnless(sys.platform == "win32", "requires Windows")
    def test_subprocess_call_windows_path(self):
        self.runner.command = r".\script.bat"
        self.evaluate()
        command = self.subprocess_call.mock_calls[0][1][0]
        self.assertEqual(command, r".\script.bat")

    def test_env_vars(self):
        self.evaluate(build_info={"my": "var", "int": 15})
        expected = {
            "MOZREGRESSION_MY": "var",
            "MOZREGRESSION_INT": "15",
            "MOZREGRESSION_APP_NAME": "myapp",
        }
        passed_env = self.subprocess_call.mock_calls[0][2]["env"]
        self.assertTrue(set(expected).issubset(set(passed_env)))

    @unittest.skipIf(sys.platform == "win32", "args is a string on Windows")
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

    @unittest.skipUnless(sys.platform == "win32", "requires Windows")
    def test_command_placeholder_replaced_windows(self):
        self.runner.command = 'run {app_name} "1"'
        self.evaluate()
        command = self.subprocess_call.mock_calls[0][1][0]
        self.assertEqual(command, 'run myapp "1"')

        self.runner.command = "run '{binary}' \"{foo}\""
        self.launcher.binary = "mybinary"
        self.evaluate(build_info={"foo": 12})
        command = self.subprocess_call.mock_calls[0][1][0]
        self.assertEqual(command, "run 'mybinary' \"12\"")

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


class TestAgentTestRunner(unittest.TestCase):
    def setUp(self):
        self.runner = test_runner.AgentTestRunner("check the page", min_version=100)
        self.launcher = Mock(binary="/path/to/firefox")
        self.launcher.get_app_info.return_value = {"application_version": "128.0"}

    @patch("mozregression.test_runner.create_launcher")
    @patch("mozregression.test_runner.subprocess.run")
    def evaluate(self, run, create_launcher, stdout=None, returncode=0, run_effect=None):
        create_launcher.return_value = Launcher(self.launcher)
        proc = Mock(returncode=returncode, stdout=stdout or "", stderr="")
        run.return_value = proc
        if run_effect:
            run.side_effect = run_effect
        self.subprocess_run = run
        return self.runner.evaluate(mockinfo(to_dict=lambda: {}))

    def test_create(self):
        self.assertEqual(self.runner.instruction, "check the page")
        self.assertEqual(self.runner.min_version, 100)

    def test_evaluate_good(self):
        verdict = self.evaluate(stdout='{"result": "Looks fine. GOOD"}')
        self.assertEqual("g", verdict)

    def test_evaluate_bad(self):
        verdict = self.evaluate(stdout='{"result": "The box is missing. BAD"}')
        self.assertEqual("b", verdict)

    def test_evaluate_plain_text_output(self):
        # output that is not JSON is scanned directly for the verdict
        verdict = self.evaluate(stdout="some logs\nBAD\n")
        self.assertEqual("b", verdict)

    def test_evaluate_last_verdict_wins(self):
        verdict = self.evaluate(stdout='{"result": "first I thought BAD but it is GOOD"}')
        self.assertEqual("g", verdict)

    def test_command_built(self):
        self.evaluate(stdout='{"result": "GOOD"}')
        command = self.subprocess_run.mock_calls[0][1][0]
        self.assertEqual(command[0], "claude")
        self.assertIn("--mcp-config", command)
        self.assertIn("mcp__firefox-devtools", command)

    def test_verdict_uses_cli_default_model_and_budget(self):
        # the verdict agent drives the browser, so it keeps the claude CLI's
        # default model/effort (no --model/--effort forced) but stays capped.
        self.evaluate(stdout='{"result": "GOOD"}')
        command = self.subprocess_run.mock_calls[0][1][0]
        self.assertNotIn("--model", command)
        self.assertNotIn("--effort", command)
        self.assertEqual(command[command.index("--max-budget-usd") + 1], "10.0")

    def test_strict_mcp_config_by_default(self):
        self.evaluate(stdout='{"result": "GOOD"}')
        command = self.subprocess_run.mock_calls[0][1][0]
        self.assertIn("--strict-mcp-config", command)

    def test_allow_other_mcp_drops_strict_flag(self):
        self.runner = test_runner.AgentTestRunner("check", min_version=100, allow_other_mcp=True)
        self.evaluate(stdout='{"result": "GOOD"}')
        command = self.subprocess_run.mock_calls[0][1][0]
        self.assertNotIn("--strict-mcp-config", command)

    def test_max_budget_override(self):
        self.runner = test_runner.AgentTestRunner("check", min_version=100, max_budget_usd=2.5)
        self.evaluate(stdout='{"result": "GOOD"}')
        command = self.subprocess_run.mock_calls[0][1][0]
        self.assertEqual(command[command.index("--max-budget-usd") + 1], "2.5")

    def test_mcp_config_reuses_cached_package_by_default(self):
        with patch("mozregression.test_runner.json.dump") as dump:
            self.evaluate(stdout='{"result": "GOOD"}')
            config = dump.mock_calls[0][1][0]
        args = config["mcpServers"]["firefox-devtools"]["args"]
        self.assertIn("--prefer-offline", args)
        self.assertIn(test_runner.AgentTestRunner.MCP_PACKAGE, args)
        self.assertNotIn(test_runner.AgentTestRunner.MCP_PACKAGE + "@latest", args)

    def test_mcp_config_recheck_fetches_latest(self):
        self.runner = test_runner.AgentTestRunner("check", min_version=100, recheck_mcp=True)
        with patch("mozregression.test_runner.json.dump") as dump:
            self.evaluate(stdout='{"result": "GOOD"}')
            config = dump.mock_calls[0][1][0]
        args = config["mcpServers"]["firefox-devtools"]["args"]
        self.assertIn("--prefer-online", args)
        self.assertIn(test_runner.AgentTestRunner.MCP_PACKAGE + "@latest", args)

    def test_headless_and_model_forwarded(self):
        self.runner = test_runner.AgentTestRunner(
            "check", min_version=100, headless=True, model="claude-x"
        )
        with patch("mozregression.test_runner.json.dump") as dump:
            self.evaluate(stdout='{"result": "GOOD"}')
            config = dump.mock_calls[0][1][0]
        args = config["mcpServers"]["firefox-devtools"]["args"]
        self.assertIn("--firefox-path", args)
        self.assertIn("/path/to/firefox", args)
        self.assertIn("--headless", args)
        command = self.subprocess_run.mock_calls[0][1][0]
        self.assertIn("--model", command)
        self.assertIn("claude-x", command)

    def test_unsupported_version(self):
        self.launcher.get_app_info.return_value = {"application_version": "96.0"}
        self.assertRaises(errors.UnsupportedVersionError, self.evaluate)

    def test_unknown_version_passes_to_agent(self):
        # if mozversion can't report a version, defer to the per-build agent
        self.launcher.get_app_info.return_value = {}
        verdict = self.evaluate(stdout='{"result": "GOOD"}')
        self.assertEqual("g", verdict)

    def test_no_verdict_in_output(self):
        self.assertRaisesRegex(
            errors.TestCommandError, "verdict", self.evaluate, stdout='{"result": "no idea"}'
        )

    def test_nonzero_returncode(self):
        self.assertRaisesRegex(errors.TestCommandError, "exited", self.evaluate, returncode=1)

    def test_claude_missing(self):
        self.assertRaisesRegex(
            errors.TestCommandError, "not found", self.evaluate, run_effect=OSError
        )

    def test_run_once(self):
        self.runner.evaluate = Mock(return_value="g")
        build_info = Mock()
        self.assertEqual(self.runner.run_once(build_info), 0)
        self.runner.evaluate.assert_called_once_with(build_info)

    @patch("mozregression.test_runner.shutil.which")
    @patch("mozregression.test_runner.subprocess.run")
    def check_prerequisites(self, run, which, missing=(), validation='{"result": "VALID"}'):
        which.side_effect = lambda exe: None if exe in missing else "/usr/bin/" + exe
        run.return_value = Mock(returncode=0, stdout=validation, stderr="")
        self.subprocess_run = run
        return self.runner.check_prerequisites()

    def test_check_prerequisites_ok(self):
        # claude + npx present, prompt validated: no error
        self.check_prerequisites()
        # the validation call does not enable any MCP/tools
        command = self.subprocess_run.mock_calls[0][1][0]
        self.assertEqual(command[0], "claude")
        self.assertNotIn("--mcp-config", command)

    def test_validation_uses_fast_model(self):
        # the validation step is a trivial text check, so it always uses the
        # fast model at low effort regardless of --prompt-model.
        self.runner = test_runner.AgentTestRunner("check", min_version=100, model="sonnet")
        self.check_prerequisites()
        command = self.subprocess_run.mock_calls[0][1][0]
        self.assertEqual(command[command.index("--model") + 1], "haiku")
        self.assertEqual(command[command.index("--effort") + 1], "low")

    def test_check_prerequisites_claude_missing(self):
        self.assertRaisesRegex(
            errors.TestCommandError, "claude", self.check_prerequisites, missing=("claude",)
        )

    def test_check_prerequisites_npx_missing(self):
        self.assertRaisesRegex(
            errors.TestCommandError, "npx", self.check_prerequisites, missing=("npx",)
        )

    def test_check_prerequisites_invalid_prompt(self):
        self.assertRaisesRegex(
            errors.TestCommandError,
            "usable",
            self.check_prerequisites,
            validation='{"result": "INVALID: too vague"}',
        )


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
