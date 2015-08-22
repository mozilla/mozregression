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

from requests.exceptions import RequestException

from mozregression import __version__
from mozregression.cli import cli
from mozregression.errors import MozRegressionError
from mozregression.bisector import BisectRunner
from mozregression.launchers import REGISTRY as APP_REGISTRY
from mozregression.network import set_http_session


class ResumeInfoBisectRunner(BisectRunner):
    def do_bisect(self, handler, good, bad, **kwargs):
        try:
            return BisectRunner.do_bisect(self, handler, good, bad, **kwargs)
        except (KeyboardInterrupt, MozRegressionError, RequestException):
            if handler.good_revision is not None and \
                    handler.bad_revision is not None:
                atexit.register(self.on_exit_print_resume_info, handler)
            raise

    def on_exit_print_resume_info(self, handler):
        handler.print_range()
        self.print_resume_info(handler)


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


def bisect_inbounds(runner, options):
    return runner.bisect_inbound(options.last_good_revision,
                                 options.first_bad_revision)


def bisect_nightlies(runner, options):
    return runner.bisect_nightlies(options.good_date, options.bad_date)


def main(argv=None):
    """
    main entry point of mozregression command line.
    """
    config = cli(argv=argv)

    try:
        check_mozregression_version(config.logger)
        config.validate()
        set_http_session(get_defaults={"timeout": config.options.http_timeout})
        runner = ResumeInfoBisectRunner(config.fetch_config,
                                        config.test_runner,
                                        config.options)

        launcher_class = APP_REGISTRY.get(config.fetch_config.app_name)
        launcher_class.check_is_runnable()

        if config.action == "bisect_nightlies":
            bisect = bisect_nightlies
        else:
            bisect = bisect_inbounds
        sys.exit(bisect(runner, config.options))
    except KeyboardInterrupt:
        sys.exit("\nInterrupted.")
    except (MozRegressionError, RequestException) as exc:
        config.logger.error(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
