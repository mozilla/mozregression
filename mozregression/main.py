#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Entry point for the mozregression command line.
"""

import sys
import requests
import atexit
import pipes
import tempfile
import mozfile

from mozlog.structuredlog import get_default_logger
from requests.exceptions import RequestException

from mozregression import __version__
from mozregression.cli import cli
from mozregression.errors import MozRegressionError
from mozregression.bisector import (Bisector, NightlyHandler, InboundHandler,
                                    Bisection)
from mozregression.launchers import REGISTRY as APP_REGISTRY
from mozregression.network import set_http_session
from mozregression.test_runner import ManualTestRunner, CommandTestRunner
from mozregression.download_manager import BuildDownloadManager


class Application(object):
    def __init__(self, fetch_config, options):
        self.fetch_config = fetch_config
        self.options = options
        self._test_runner = None
        self._bisector = None
        self._build_download_manager = None
        self._logger = get_default_logger('main')
        self._download_dir = options.persist
        self._rm_download_dir = False
        if options.persist is None:
            self._download_dir = tempfile.mkdtemp()
            self._rm_download_dir = True

    def clear(self):
        if self._build_download_manager:
            # cancel all possible downloads
            self._build_download_manager.cancel()
        if self._rm_download_dir:
            mozfile.remove(self._download_dir)

    @property
    def test_runner(self):
        if self._test_runner is None:
            if self.options.command is None:
                self._test_runner = ManualTestRunner(launcher_kwargs=dict(
                    addons=self.options.addons,
                    profile=self.options.profile,
                    cmdargs=self.options.cmdargs,
                    preferences=self.options.preferences,
                ))
            else:
                self._test_runner = CommandTestRunner(self.options.command)
        return self._test_runner

    @property
    def bisector(self):
        if self._bisector is None:
            self._bisector = Bisector(
                self.fetch_config, self.test_runner,
                self.build_download_manager,
                dl_in_background=self.options.background_dl
            )
        return self._bisector

    @property
    def build_download_manager(self):
        if self._build_download_manager is None:
            background_dl_policy = self.options.background_dl_policy
            if self.options.persist is None:
                # cancel background downloads forced
                background_dl_policy = "cancel"
            self._build_download_manager = BuildDownloadManager(
                self._download_dir,
                background_dl_policy=background_dl_policy
            )
        return self._build_download_manager

    def bisect_nightlies(self):
        good_date, bad_date = self.options.good_date, self.options.bad_date
        handler = NightlyHandler(find_fix=self.options.find_fix)
        result = self._do_bisect(handler, good_date, bad_date)
        if result == Bisection.FINISHED:
            self._logger.info("Got as far as we can go bisecting nightlies...")
            handler.print_range()
            if self.fetch_config.can_go_inbound():
                good_rev, bad_rev = handler.find_inbound_changesets()
                return self._bisect_inbounds(good_rev, bad_rev)
            else:
                message = ("Can not bisect inbound for application `%s`"
                           % self.fetch_config.app_name)
                if self.fetch_config.is_inbound():
                    # the config is able to bissect inbound but not
                    # for this repo.
                    message += (" because the repo `%s` was specified"
                                % self.options.repo)
                self._logger.info(message + '.')
        elif result == Bisection.USER_EXIT:
            self._print_resume_info(handler)
        else:
            # NO_DATA
            self._logger.info("Unable to get valid builds within the given"
                              " range. You should try to launch mozregression"
                              " again with a larger date range.")
            return 1
        return 0

    def bisect_inbounds(self):
        return self._bisect_inbounds(self.options.last_good_revision,
                                     self.options.first_bad_revision)

    def _bisect_inbounds(self, good_rev, bad_rev):
        self._logger.info("Getting inbound builds between %s and %s"
                          % (good_rev, bad_rev))
        handler = InboundHandler(find_fix=self.options.find_fix)
        result = self._do_bisect(handler, good_rev, bad_rev)
        if result == Bisection.FINISHED:
            self._logger.info("Oh noes, no (more) inbound revisions :(")
            handler.print_range()
            if handler.good_revision == handler.bad_revision:
                self._logger.warning(
                    "It seems that you used two changesets that are in"
                    " in the same push. Check the pushlog url."
                )
        elif result == Bisection.USER_EXIT:
            self._print_resume_info(handler)
        else:
            # NO_DATA. With inbounds, this can not happen if changesets
            # are incorrect - so builds are probably too old
            self._logger.info(
                'There are no build artifacts on inbound for these'
                ' changesets (they are probably too old).')
            return 1
        return 0

    def _do_bisect(self, handler, good, bad):
        try:
            return self.bisector.bisect(handler, good, bad)
        except (KeyboardInterrupt, MozRegressionError, RequestException):
            if handler.good_revision is not None and \
                    handler.bad_revision is not None:
                atexit.register(self._on_exit_print_resume_info, handler)
            raise

    def _print_resume_info(self, handler):
        if isinstance(handler, NightlyHandler):
            info = '--good=%s --bad=%s' % (handler.good_date, handler.bad_date)
        else:
            info = ('--good-rev=%s --bad-rev=%s'
                    % (handler.good_revision, handler.bad_revision))
        options = self.options
        info += ' --app=%s' % options.app
        if options.find_fix:
            info += ' --find-fix'
        if len(options.addons) > 0:
            info += ' ' + ' '.join('--addon=%s' % pipes.quote(addon)
                                   for addon in options.addons)
        if options.cmdargs:
            info += ' ' + ' '.join('--arg=%s' % pipes.quote(arg)
                                   for arg in options.cmdargs)
        if options.profile is not None:
            info += ' --profile=%s' % pipes.quote(options.profile)
        if options.inbound_branch is not None:
            info += ' --inbound-branch=%s' % options.inbound_branch
        if options.repo is not None:
            info += ' --repo=%s' % options.repo
        info += ' --bits=%s' % options.bits
        if options.persist is not None:
            info += ' --persist=%s' % pipes.quote(options.persist)

        self._logger.info('To resume, run:')
        self._logger.info('mozregression %s' % info)

    def _on_exit_print_resume_info(self, handler):
        handler.print_range()
        self._print_resume_info(handler)


def check_mozregression_version(logger):
    url = "https://pypi.python.org/pypi/mozregression/json"
    try:
        mozregression_version = \
            requests.get(url, timeout=10).json()['info']['version']
    except (RequestException, KeyError, ValueError):
        logger.critical("Unable to get latest version from pypi.")
        return

    if __version__ != mozregression_version:
        logger.warning("You are using mozregression version %s, "
                       "however version %s is available."
                       % (__version__, mozregression_version))

        logger.warning("You should consider upgrading via the 'pip install"
                       " --upgrade mozregression' command.")


def main(argv=None):
    """
    main entry point of mozregression command line.
    """
    config = cli(argv=argv)
    app = None
    try:
        check_mozregression_version(config.logger)
        config.validate()
        set_http_session(get_defaults={"timeout": config.options.http_timeout})
        app = Application(config.fetch_config, config.options)

        launcher_class = APP_REGISTRY.get(config.fetch_config.app_name)
        launcher_class.check_is_runnable()

        method = getattr(app, config.action)
        sys.exit(method())

    except KeyboardInterrupt:
        sys.exit("\nInterrupted.")
    except (MozRegressionError, RequestException) as exc:
        config.logger.error(str(exc))
        sys.exit(1)
    finally:
        if app:
            app.clear()

if __name__ == "__main__":
    main()
