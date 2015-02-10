#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
This module implements a :class:`TestRunner` interface for testing builds
and a default implementation :class:`ManualTestRunner`.
"""

from mozlog.structured import get_default_logger
import subprocess
import shlex
import os
import tempfile
import mozfile

from mozregression.launchers import create_launcher
from mozregression.errors import TestCommandError


class TestRunner(object):
    """
    Abstract class that allows to test a build.

    :meth:`evaluate` must be implemented by subclasses.
    """
    def __init__(self, fetch_config, persist=None, launcher_kwargs=None):
        self.fetch_config = fetch_config
        self.persist = persist
        self.launcher_kwargs = launcher_kwargs or {}
        self.logger = get_default_logger('Test Runner')

    def create_launcher(self, build_info):
        """
        Create and returns a :class:`mozregression.launchers.Launcher`.
        """
        if build_info['build_type'] == 'nightly':
            date = build_info['build_date']
            nightly_repo = self.fetch_config.get_nightly_repo(date)
            persist_prefix = '%s--%s--' % (date, nightly_repo)
            self.logger.info("Running nightly for %s" % date)
        else:
            persist_prefix = '%s--%s--' % (build_info['timestamp'],
                                           self.fetch_config.inbound_branch)
            self.logger.info("Testing inbound build with timestamp %s,"
                             " revision %s"
                             % (build_info['timestamp'],
                                build_info['revision']))
        build_url = build_info['build_url']
        return create_launcher(self.fetch_config.app_name,
                               build_url,
                               persist=self.persist,
                               persist_prefix=persist_prefix)

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

        :param build_info: is a dict containing information about the build
                           to test. It is ensured to have the following keys:
                            - build_type ('nightly' or 'inbound')
                            - build_url
                            - repository (mercurial repository of the build)
                            - changeset (mercurial changeset of the build)
                           Also, if the build_type is 'nightly':
                            - build_date (datetime.date instance)
                           Or 'inbound':
                            - timestamp: timestamp of the build
                            - revision (short version of changeset)
        :param allow_back: indicate if the back command should be proposed.
        """
        raise NotImplementedError


class ManualTestRunner(TestRunner):
    """
    A TestRunner subclass that run builds and ask for evaluation by
    prompting in the terminal.
    """
    def __init__(self, fetch_config, persist=None, launcher_kwargs=None):
        self.delete_persist = False
        if persist is None:
            # always keep the downloaded files for manual runner
            # this allows to not re-download a file if a user retry a build.
            persist = tempfile.mkdtemp()
            self.delete_persist = True
        TestRunner.__init__(self, fetch_config, persist=persist,
                            launcher_kwargs=launcher_kwargs)

    def __del__(self):
        if self.delete_persist:
            mozfile.remove(self.persist)

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
        formatted_options = (', '.join(["'%s'" % o for o in options[:-1]])
                             + " or '%s'" % options[-1])
        verdict = ""
        while verdict not in allowed_inputs:
            verdict = raw_input("Was this %s build good, bad, or broken?"
                                " (type %s and press Enter): "
                                % (build_info['build_type'],
                                   formatted_options))

        if verdict == 'back':
            return 'back'
        # shorten verdict to one character for processing...
        return verdict[0]

    def evaluate(self, build_info, allow_back=False):
        launcher = self.create_launcher(build_info)
        launcher.start(**self.launcher_kwargs)
        app_infos = launcher.get_app_info()
        verdict = self.get_verdict(build_info, allow_back)
        launcher.stop()
        return verdict, app_infos


def _raise_command_error(exc, msg=''):
    raise TestCommandError("Unable to run the test command%s: `%s`"
                           % (msg, exc))


class CommandTestRunner(TestRunner):
    """
    A TestRunner subclass that evaluate builds given a shell command.

    Some variables may be used to evaluate the builds:
     - variables referenced in :meth:`TestRunner.evaluate`
     - app_name (the tested application name: firefox, b2g...)
     - binary (the path to the binary when applicable - not for fennec)

    These variables can be used in two ways:
    1. as environment variables. 'MOZREGRESSION_' is prepended and the
       variables names are upcased. Example: MOZREGRESSION_BINARY
    2. as placeholders in the command line. variables names must be enclosed
       with curly brackets. Example:
       `mozmill -app firefox -b {binary} -t path/to/test.js`
    """
    def __init__(self, fetch_config, command, **kwargs):
        TestRunner.__init__(self, fetch_config, **kwargs)
        self.command = command

    def evaluate(self, build_info, allow_back=False):
        launcher = self.create_launcher(build_info)
        app_info = launcher.get_app_info()
        variables = dict((k, str(v)) for k, v in build_info.iteritems())
        variables['app_name'] = launcher.app_name
        if hasattr(launcher, 'binary'):
            variables['binary'] = launcher.binary

        env = dict(os.environ)
        for k, v in variables.iteritems():
            env['MOZREGRESSION_' + k.upper()] = v
        try:
            command = self.command.format(**variables)
        except KeyError as exc:
            _raise_command_error(exc, ' (formatting error)')
        self.logger.info('Running test command: `%s`' % command)
        cmdlist = shlex.split(command)
        try:
            retcode = subprocess.call(cmdlist, env=env)
        except IndexError:
            _raise_command_error("Empty command")
        except OSError as exc:
            _raise_command_error(exc,
                                 " (%s not found or not executable)"
                                 % cmdlist[0])
        self.logger.info('Test command result: %d (build is %s)'
                         % (retcode, 'good' if retcode == 0 else 'bad'))
        return 'g' if retcode == 0 else 'b', app_info
