"""
This module implements a :class:`TestRunner` interface for testing builds
and a default implementation :class:`ManualTestRunner`.
"""

from __future__ import absolute_import, print_function

import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from abc import ABCMeta, abstractmethod

from mozlog import get_proxy_logger

from mozregression.errors import LauncherError, TestCommandError, UnsupportedVersionError
from mozregression.launchers import create_launcher as mozlauncher

LOG = get_proxy_logger("Test Runner")


def create_launcher(build_info):
    """
    Create and returns a :class:`mozregression.launchers.Launcher`.
    """
    if build_info.build_type == "nightly":
        if isinstance(build_info.build_date, datetime.datetime):
            desc = "for buildid %s" % build_info.build_date.strftime("%Y%m%d%H%M%S")
        else:
            desc = "for %s" % build_info.build_date
    else:
        desc = "built on %s, revision %s" % (
            build_info.build_date,
            build_info.short_changeset,
        )
    LOG.info("Running %s build %s" % (build_info.repo_name, desc))

    return mozlauncher(build_info)


class TestRunner(metaclass=ABCMeta):
    """
    Abstract class that allows to test a build.

    :meth:`evaluate` must be implemented by subclasses.
    """

    @abstractmethod
    def evaluate(self, build_info, allow_back=False):
        """
        Evaluate a given build. Must returns a tuple of (verdict, app_info).

        The verdict must be a letter that indicate the state of the build:
        'g', 'b', 's', 'r' or 'e' respectively for 'good', 'bad', 'skip',
        'retry' or 'exit'. If **allow_back** is True, it is also possible
        to return 'back'.

        The app_info is the return value of the
        :meth:`mozregression.launchers.Launcher.get_app_info` for this
        particular build.

        :param build_path: the path to the build file to test
        :param build_info: a :class:`mozrgression.uild_info.BuildInfo` instance
        :param allow_back: indicate if the back command should be proposed.
        """
        raise NotImplementedError

    @abstractmethod
    def run_once(self, build_info):
        """
        Run the given build and wait for its completion. Return the error
        code when available.
        """
        raise NotImplementedError

    def index_to_try_after_skip(self, build_range):
        """
        Return the index of the build to use after a build was skipped.

        By default this only returns the mid point of the remaining range.
        """
        return build_range.mid_point()


class ManualTestRunner(TestRunner):
    """
    A TestRunner subclass that run builds and ask for evaluation by
    prompting in the terminal.
    """

    def __init__(self, launcher_kwargs=None):
        TestRunner.__init__(self)
        self.launcher_kwargs = launcher_kwargs or {}

    def get_verdict(self, build_info, allow_back):
        """
        Ask and returns the verdict.
        """
        options = ["good", "bad", "skip", "retry", "exit"]
        if allow_back:
            options.insert(-1, "back")
        # allow user to just type one letter
        allowed_inputs = options + [o[0] for o in options]
        # format options to nice printing
        formatted_options = ", ".join(["'%s'" % o for o in options[:-1]]) + " or '%s'" % options[-1]
        verdict = ""
        while verdict not in allowed_inputs:
            verdict = input(
                "Was this %s build good, bad, or broken?"
                " (type %s and press Enter): " % (build_info.build_type, formatted_options)
            )

        if verdict == "back":
            return "back"
        # shorten verdict to one character for processing...
        return verdict[0]

    def evaluate(self, build_info, allow_back=False):
        with create_launcher(build_info) as launcher:
            launcher.start(**self.launcher_kwargs)
            build_info.update_from_app_info(launcher.get_app_info())
            verdict = self.get_verdict(build_info, allow_back)
            try:
                launcher.stop()
            except LauncherError:
                # we got an error on process termination, but user
                # already gave the verdict, so pass this "silently"
                # (it would be logged from the launcher anyway)
                launcher._running = False
        return verdict

    def run_once(self, build_info):
        with create_launcher(build_info) as launcher:
            launcher.start(**self.launcher_kwargs)
            build_info.update_from_app_info(launcher.get_app_info())
            return launcher.wait()

    def index_to_try_after_skip(self, build_range):
        mid = TestRunner.index_to_try_after_skip(self, build_range)
        build_range_len = len(build_range)
        if build_range_len <= 3:
            # do not even ask if there is only one build to choose
            return mid
        min = -mid + 1
        max = build_range_len - mid - 2
        valid_range = list(range(min, max + 1))
        print(
            "Build was skipped. You can manually choose a new build to"
            " test, to be able to get out of a broken build range."
        )
        print(
            "Please type the index of the build you would like to try - the"
            " index is 0-based on the middle of the remaining build range."
        )
        print("You can choose a build index between [%d, %d]:" % (min, max))
        while True:
            value = input("> ")
            try:
                index = int(value)
                if index in valid_range:
                    return mid + index
            except ValueError:
                pass


def _raise_command_error(exc, msg=""):
    raise TestCommandError("Unable to run the test command%s: `%s`" % (msg, exc))


class CommandTestRunner(TestRunner):
    """
    A TestRunner subclass that evaluate builds given a shell command.

    Some variables may be used to evaluate the builds:
     - variables referenced in :meth:`TestRunner.evaluate`
     - app_name (the tested application name: firefox, ...)
     - binary (the path to the binary when applicable - not for fennec)

    These variables can be used in two ways:
    1. as environment variables. 'MOZREGRESSION_' is prepended and the
       variables names are upcased. Example: MOZREGRESSION_BINARY
    2. as placeholders in the command line. variables names must be enclosed
       with curly brackets. Example:
       `mozmill -app firefox -b {binary} -t path/to/test.js`
    """

    def __init__(self, command):
        TestRunner.__init__(self)
        self.command = command

    def evaluate(self, build_info, allow_back=False):
        with create_launcher(build_info) as launcher:
            build_info.update_from_app_info(launcher.get_app_info())
            variables = {k: v for k, v in build_info.to_dict().items()}
            if hasattr(launcher, "binary"):
                variables["binary"] = launcher.binary

            env = dict(os.environ)
            for k, v in variables.items():
                env["MOZREGRESSION_" + k.upper()] = str(v)
            try:
                command = self.command.format(**variables)
            except KeyError as exc:
                _raise_command_error(exc, " (formatting error)")
            command = os.path.expanduser(command)
            LOG.info("Running test command: `%s`" % command)

            # `shlex.split` does parsing and escaping that isn't compatible with Windows.
            if sys.platform == "win32":
                cmdlist = command
            else:
                cmdlist = shlex.split(command)

            try:
                retcode = subprocess.call(cmdlist, env=env)
            except IndexError:
                _raise_command_error("Empty command")
            except OSError as exc:
                _raise_command_error(
                    exc,
                    " (%s not found or not executable)"
                    % (command if sys.platform == "win32" else cmdlist[0]),
                )
        LOG.info(
            "Test command result: %d (build is %s)" % (retcode, "good" if retcode == 0 else "bad")
        )
        return "g" if retcode == 0 else "b"

    def run_once(self, build_info):
        return 0 if self.evaluate(build_info) == "g" else 1


# Verdict tokens the agent is instructed to emit, matched as standalone words.
_VERDICT_RE = re.compile(r"\b(GOOD|BAD)\b")


def _major_version(version):
    """
    Return the integer major version from a version string like "128.0.1",
    or None if it can not be parsed.
    """
    if not version:
        return None
    match = re.match(r"\s*(\d+)", str(version))
    return int(match.group(1)) if match else None


class AgentTestRunner(TestRunner):
    """
    A TestRunner subclass that evaluates builds with an LLM agent driving the
    Firefox DevTools MCP (https://github.com/mozilla/firefox-devtools-mcp).

    Given a natural language instruction, the agent inspects the running build
    via the MCP and decides whether it is good or bad. This is the higher level
    equivalent of :class:`CommandTestRunner` (similar to ``git bisect run``).

    The agent is run by shelling out to the ``claude`` CLI in headless mode,
    pointed at the MCP through a generated ``--mcp-config``. The MCP launches
    the build itself, so this runner installs the build (to obtain the binary
    path) but does not start it.

    Requires the ``claude`` CLI (installed and authenticated) and Node/``npx``
    on the PATH.
    """

    #: Name used for the MCP server in the generated config, also the prefix of
    #: the tool names exposed to the agent (``mcp__firefox-devtools__*``).
    MCP_SERVER_NAME = "firefox-devtools"

    #: npm package providing the Firefox DevTools MCP server.
    MCP_PACKAGE = "@mozilla/firefox-devtools-mcp"

    #: Model/effort for the up-front prompt validation only. That is a trivial
    #: text yes/no check (it does not drive the MCP), so a fast, cheap model at
    #: low effort is plenty. The per-build verdict agent, which actually drives
    #: the browser, uses the `claude` CLI's default model unless overridden with
    #: ``--prompt-model`` -- a weaker model there misreads multi-step
    #: instructions and navigates to the wrong place.
    VALIDATION_MODEL = "haiku"
    VALIDATION_EFFORT = "low"

    def __init__(
        self,
        instruction,
        min_version=100,
        headless=False,
        model=None,
        recheck_mcp=False,
        allow_other_mcp=False,
        max_budget_usd=10.0,
    ):
        TestRunner.__init__(self)
        self.instruction = instruction
        self.min_version = min_version
        self.headless = headless
        self.model = model
        self.recheck_mcp = recheck_mcp
        self.allow_other_mcp = allow_other_mcp
        self.max_budget_usd = max_budget_usd

    def check_prerequisites(self):
        """
        Fail fast, before any bisection happens, if the agent can not run or if
        the instruction is not usable. Checks that the required executables are
        available and that the prompt is able to yield a good/bad verdict.
        """
        for executable in ("claude", "npx"):
            if shutil.which(executable) is None:
                raise TestCommandError(
                    "`%s` is required for --prompt but was not found on the"
                    " PATH. Install it (and run `claude` once to authenticate)"
                    " before using --prompt." % executable
                )
        self._validate_prompt()

    def _validate_prompt(self):
        """
        Ask the agent whether the instruction can produce a clear good/bad
        determination, and raise :class:`TestCommandError` if it can not.
        """
        meta_prompt = (
            "You are validating an instruction that will be used to judge"
            " whether a Firefox build is GOOD or BAD during a regression"
            " bisection. A usable instruction describes something observable in"
            " the browser that maps to a clear good-or-bad outcome.\n\n"
            'Instruction: "%s"\n\n'
            "If the instruction is usable, reply with exactly: VALID\n"
            "Otherwise reply with: INVALID: <one sentence on what is missing>" % self.instruction
        )
        command = (
            ["claude", "-p", meta_prompt, "--output-format", "json"]
            + ["--model", self.VALIDATION_MODEL, "--effort", self.VALIDATION_EFFORT]
            + self._budget_flags()
        )
        LOG.info("Validating --prompt instruction with the agent...")
        proc = self._invoke_claude(command)
        if proc.returncode != 0:
            _raise_command_error(
                "claude exited with code %d: %s" % (proc.returncode, proc.stderr.strip())
            )
        text = self._result_text(proc.stdout)
        if "VALID" not in text.upper() or "INVALID" in text.upper():
            raise TestCommandError(
                "the --prompt instruction does not look usable for a good/bad"
                " verdict: %s" % text.strip()
            )
        LOG.info("--prompt instruction validated.")

    def _budget_flags(self):
        """
        Per-call spending cap shared by the validation and verdict claude calls.
        """
        if self.max_budget_usd is not None:
            return ["--max-budget-usd", str(self.max_budget_usd)]
        return []

    def _invoke_claude(self, command):
        try:
            return subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
        except OSError as exc:
            _raise_command_error(exc, " (claude not found or not executable)")

    def _check_version(self, app_info):
        version = app_info.get("application_version")
        major = _major_version(version)
        if major is not None and major < self.min_version:
            raise UnsupportedVersionError(version, self.min_version)

    def _mcp_config(self, binary):
        # By default reuse whatever npx already has cached and stay offline, so
        # each build in the bisection does not pay a registry round-trip (and
        # uses a consistent version). --prompt-recheck-mcp forces npx to fetch
        # the latest published version instead.
        if self.recheck_mcp:
            args = ["-y", "--prefer-online", self.MCP_PACKAGE + "@latest"]
        else:
            args = ["-y", "--prefer-offline", self.MCP_PACKAGE]
        args += ["--firefox-path", binary]
        if self.headless:
            args.append("--headless")
        return {
            "mcpServers": {
                self.MCP_SERVER_NAME: {
                    "command": "npx",
                    "args": args,
                }
            }
        }

    def _build_prompt(self):
        return (
            "You are evaluating a Firefox build during a regression bisection."
            " Use the Firefox DevTools MCP tools to investigate the running"
            " build, then decide whether the build is GOOD or BAD according to"
            " this instruction:\n\n"
            "%s\n\n"
            "When you are done investigating, reply with exactly one word on"
            " the final line: GOOD if the build behaves as expected, or BAD if"
            " it exhibits the problem." % self.instruction
        )

    @staticmethod
    def _result_text(stdout):
        """
        Return the agent's final answer text from the ``claude`` output. With
        ``--output-format json`` the answer is wrapped in a "result" field;
        otherwise the raw stdout is returned.
        """
        try:
            payload = json.loads(stdout)
        except ValueError:
            return stdout
        if isinstance(payload, dict):
            return payload.get("result") or ""
        return stdout

    @classmethod
    def _parse_verdict(cls, stdout):
        """
        Extract a 'g'/'b' verdict from the ``claude`` output, or return None if
        no verdict could be determined.
        """
        matches = _VERDICT_RE.findall(cls._result_text(stdout))
        if not matches:
            return None
        # the verdict is the last standalone GOOD/BAD token emitted.
        return "g" if matches[-1] == "GOOD" else "b"

    def _run_agent(self, binary, build_info):
        config = self._mcp_config(binary)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", prefix="mozregression-mcp-", delete=False
        ) as fp:
            json.dump(config, fp)
            config_path = fp.name
        try:
            command = [
                "claude",
                "-p",
                self._build_prompt(),
                "--mcp-config",
                config_path,
                "--allowedTools",
                "mcp__%s" % self.MCP_SERVER_NAME,
                "--output-format",
                "json",
                "--permission-mode",
                "bypassPermissions",
            ]
            if not self.allow_other_mcp:
                # only load the Firefox DevTools MCP from our generated config,
                # ignoring any other MCP servers the user has configured.
                command.append("--strict-mcp-config")
            # the verdict agent drives the browser, so it keeps the claude CLI's
            # default model/effort unless --prompt-model overrides it.
            if self.model:
                command += ["--model", self.model]
            command += self._budget_flags()
            LOG.info("Running agent with instruction: %r" % self.instruction)
            proc = self._invoke_claude(command)
        finally:
            try:
                os.unlink(config_path)
            except OSError:
                pass

        if proc.returncode != 0:
            _raise_command_error(
                "claude exited with code %d: %s" % (proc.returncode, proc.stderr.strip())
            )
        verdict = self._parse_verdict(proc.stdout)
        if verdict is None:
            _raise_command_error(
                "could not find a GOOD/BAD verdict in the agent output:" " %s" % proc.stdout.strip()
            )
        LOG.info("Agent verdict: build is %s" % ("good" if verdict == "g" else "bad"))
        return verdict

    def evaluate(self, build_info, allow_back=False):
        with create_launcher(build_info) as launcher:
            app_info = launcher.get_app_info()
            build_info.update_from_app_info(app_info)
            self._check_version(app_info)
            return self._run_agent(launcher.binary, build_info)

    def run_once(self, build_info):
        return 0 if self.evaluate(build_info) == "g" else 1
