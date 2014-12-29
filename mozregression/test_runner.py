#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
This module implements a :class:`TestRunner` interface for testing builds
and a default implementation :class:`ManualTestRunner`.
"""

from mozlog.structured import get_default_logger

from mozregression.launchers import create_launcher


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

    def evaluate(self, build_info):
        """
        Evaluate a given build. Must returns a letter that indicate the
        state of the build: 'g', 'b', 's', 'r' or 'e' that indicates
        respectively 'good', 'bad', 'skip', 'retry' or 'exit'.

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
        """
        raise NotImplementedError


class ManualTestRunner(TestRunner):
    """
    A TestRunner subclass that run builds and ask for evaluation by
    prompting in the terminal.
    """
    def create_launcher(self, build_info):
        """
        Create and returns a :class:`mozregression.launchers.Launcher`
        that has been started.
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

    def get_verdict(self, build_info):
        """
        Ask and returns the verdict.
        """
        options = ['good', 'bad', 'skip', 'retry', 'exit']
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

        # shorten verdict to one character for processing...
        return verdict[0]

    def evaluate(self, build_info):
        launcher = self.create_launcher(build_info)
        launcher.start(**self.launcher_kwargs)
        # keep this because it prints build info
        launcher.get_app_info()
        verdict = self.get_verdict(build_info)
        launcher.stop()
        return verdict
