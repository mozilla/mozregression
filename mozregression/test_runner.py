# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
This module implements a :class:`TestRunner` interface for testing builds
and a default implementation :class:`ManualTestRunner`.
"""

from mozlog import get_proxy_logger
import subprocess
import shlex
import os
import datetime

from mozregression.launchers import create_launcher as mozlauncher
from mozregression.errors import TestCommandError, LauncherError
from abc import ABCMeta, abstractmethod

LOG = get_proxy_logger("Test Runner")


def create_launcher(build_info):
    """
    Create and returns a :class:`mozregression.launchers.Launcher`.
    """
    if build_info.build_type == 'nightly':
        if isinstance(build_info.build_date, datetime.datetime):
            desc = ("for buildid %s"
                    % build_info.build_date.strftime("%Y%m%d%H%M%S"))
        else:
            desc = "for %s" % build_info.build_date
    else:
        desc = ("built on %s, revision %s"
                % (build_info.build_date,
                   build_info.short_changeset))
    LOG.info("Running %s build %s" % (build_info.repo_name, desc))

    return mozlauncher(build_info)


class TestRunner:
    """
    Abstract class that allows to test a build.

    :meth:`evaluate` must be implemented by subclasses.
    """
    __metaclass__ = ABCMeta

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
        options = ['good', 'bad', 'skip', 'retry', 'exit']
        if allow_back:
            options.insert(-1, 'back')
        # allow user to just type one letter
        allowed_inputs = options + [o[0] for o in options]
        # format options to nice printing
        formatted_options = (', '.join(["'%s'" % o for o in options[:-1]]) +
                             " or '%s'" % options[-1])
        verdict = ""
        while verdict not in allowed_inputs:
            verdict = raw_input("Was this %s build good, bad, or broken?"
                                " (type %s and press Enter): "
                                % (build_info.build_type,
                                   formatted_options))

        if verdict == 'back':
            return 'back'
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
        valid_range = range(min, max + 1)
        print("Build was skipped. You can manually choose a new build to"
              " test, to be able to get out of a broken build range.")
        print("Please type the index of the build you would like to try - the"
              " index is 0-based on the middle of the remaining build range.")
        print "You can choose a build index between [%d, %d]:" % (min, max)
        while True:
            value = raw_input('> ')
            try:
                index = int(value)
                if index in valid_range:
                    return mid + index
            except ValueError:
                pass


def _raise_command_error(exc, msg=''):
    raise TestCommandError("Unable to run the test command%s: `%s`"
                           % (msg, exc))


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
            variables = dict((k, str(v))
                             for k, v in build_info.to_dict().iteritems())
            if hasattr(launcher, 'binary'):
                variables['binary'] = launcher.binary

            env = dict(os.environ)
            for k, v in variables.iteritems():
                env['MOZREGRESSION_' + k.upper()] = v
            try:
                command = self.command.format(**variables)
            except KeyError as exc:
                _raise_command_error(exc, ' (formatting error)')
            LOG.info('Running test command: `%s`' % command)
            cmdlist = shlex.split(command)
            try:
                retcode = subprocess.call(cmdlist, env=env)
            except IndexError:
                _raise_command_error("Empty command")
            except OSError as exc:
                _raise_command_error(exc,
                                     " (%s not found or not executable)"
                                     % cmdlist[0])
        LOG.info('Test command result: %d (build is %s)'
                 % (retcode, 'good' if retcode == 0 else 'bad'))
        return 'g' if retcode == 0 else 'b'

    def run_once(self, build_info):
        return 0 if self.evaluate(build_info) == 'g' else 1
