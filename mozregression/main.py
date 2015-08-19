#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Entry point for the mozregression command line.
"""

import mozinfo
import datetime
import sys
import atexit
import requests

import mozprofile
from mozlog.structured import commandline
from requests.exceptions import RequestException

from mozregression.cli import parse_args
from mozregression.errors import MozRegressionError, UnavailableRelease
from mozregression import __version__
from mozregression.utils import (parse_date, date_of_release,
                                 parse_bits, formatted_valid_release_dates)
from mozregression.network import set_http_session
from mozregression.fetch_configs import create_config
from mozregression.bisector import BisectRunner
from mozregression.launchers import REGISTRY as APP_REGISTRY
from mozregression.test_runner import ManualTestRunner, CommandTestRunner


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


def bisect_inbound(runner, logger):
    fetch_config = runner.fetch_config
    options = runner.options
    if not fetch_config.is_inbound():
        raise MozRegressionError('Unable to bissect inbound for `%s`'
                                 % fetch_config.app_name)
    if not options.last_good_revision or not options.first_bad_revision:
        raise MozRegressionError("If bisecting inbound, both --good-rev"
                                 " and --bad-rev must be set")
    return runner.bisect_inbound(options.last_good_revision,
                                 options.first_bad_revision)


def bisect_nightlies(runner, logger):
    default_bad_date = str(datetime.date.today())
    default_good_date = "2009-01-01"
    fetch_config = runner.fetch_config
    options = runner.options
    if options.find_fix:
        default_bad_date, default_good_date = \
            default_good_date, default_bad_date
    # TODO: currently every fetch_config is nightly aware. Shoud we test
    # for this to be sure here ?
    fetch_config.set_nightly_repo(options.repo)
    if not options.bad_release and not options.bad_date:
        options.bad_date = default_bad_date
        logger.info("No 'bad' date specified, using %s" % options.bad_date)
    elif options.bad_release and options.bad_date:
        raise MozRegressionError("Options '--bad_release' and '--bad_date'"
                                 " are incompatible.")
    elif options.bad_release:
        options.bad_date = date_of_release(options.bad_release)
        logger.info("Using 'bad' date %s for release %s"
                    % (options.bad_date, options.bad_release))
    if not options.good_release and not options.good_date:
        options.good_date = default_good_date
        logger.info("No 'good' date specified, using %s"
                    % options.good_date)
    elif options.good_release and options.good_date:
        raise MozRegressionError("Options '--good_release' and '--good_date'"
                                 " are incompatible.")
    elif options.good_release:
        options.good_date = date_of_release(options.good_release)
        logger.info("Using 'good' date %s for release %s"
                    % (options.good_date, options.good_release))

    good_date = parse_date(options.good_date)
    bad_date = parse_date(options.bad_date)
    if good_date > bad_date and not options.find_fix:
        raise MozRegressionError(("Good date %s is later than bad date %s."
                                  " Maybe you wanted to use the --find-fix"
                                  " flag ?") % (good_date, bad_date))
    elif good_date < bad_date and options.find_fix:
        raise MozRegressionError(("Bad date %s is later than good date %s."
                                  " You should not use the --find-fix flag"
                                  " in this case...") % (bad_date, good_date))

    return runner.bisect_nightlies(good_date, bad_date)


def preference(prefs_files, prefs_args):
    """
    profile preferences
    """
    # object that will hold the preferences
    prefs = mozprofile.prefs.Preferences()

    # add preferences files
    if prefs_files:
        for prefs_file in prefs_files:
            prefs.add_file(prefs_file)

    separator = ':'
    cli_prefs = []
    if prefs_args:
        for pref in prefs_args:
            if separator not in pref:
                continue
            cli_prefs.append(pref.split(separator, 1))

    # string preferences
    prefs.add(cli_prefs, cast=True)

    return prefs()


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


def cli(argv=None):
    """
    main entry point of mozregression command line.
    """
    options = parse_args(argv)
    logger = commandline.setup_logging("mozregression",
                                       options,
                                       {"mach": sys.stdout})
    check_mozregression_version(logger)

    if options.list_releases:
        print(formatted_valid_release_dates())
        sys.exit()

    set_http_session(get_defaults={"timeout": options.http_timeout})

    user_defined_bits = options.bits is not None
    options.bits = parse_bits(options.bits or mozinfo.bits)
    fetch_config = create_config(options.app, mozinfo.os, options.bits)

    if not user_defined_bits and \
            options.bits == 64 and \
            mozinfo.os == 'win' and \
            32 in fetch_config.available_bits():
        # inform users on windows that we are using 64 bit builds.
        logger.info("bits option not specified, using 64-bit builds.")

    if options.command is None:
        launcher_kwargs = dict(
            addons=options.addons,
            profile=options.profile,
            cmdargs=options.cmdargs,
            preferences=preference(options.prefs_files, options.prefs),
        )
        test_runner = ManualTestRunner(launcher_kwargs=launcher_kwargs)
    else:
        test_runner = CommandTestRunner(options.command)

    runner = ResumeInfoBisectRunner(fetch_config, test_runner, options)

    if fetch_config.is_inbound():
        # this can be useful for both inbound and nightly, because we
        # can go to inbound from nightly.
        fetch_config.set_inbound_branch(options.inbound_branch)

    # bisect inbound if last good revision or first bad revision are set
    if options.first_bad_revision or options.last_good_revision:
        bisect = bisect_inbound
    else:
        bisect = bisect_nightlies

    try:
        launcher_class = APP_REGISTRY.get(fetch_config.app_name)
        launcher_class.check_is_runnable()

        sys.exit(bisect(runner, logger))
    except KeyboardInterrupt:
        sys.exit("\nInterrupted.")
    except UnavailableRelease as exc:
        logger.error("%s\n%s" % (exc, formatted_valid_release_dates()))
        sys.exit(1)
    except (MozRegressionError, RequestException) as exc:
        logger.error(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    cli()
