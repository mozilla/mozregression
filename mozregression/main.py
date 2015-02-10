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
from argparse import ArgumentParser
from mozlog.structured import commandline, get_default_logger
from requests.exceptions import RequestException

from mozregression.errors import MozRegressionError, UnavailableRelease
from mozregression import limitedfilecache
from mozregression import __version__
from mozregression.utils import (parse_date, date_of_release,
                                 parse_bits, set_http_cache_session,
                                 formatted_valid_release_dates)
from mozregression.fetch_configs import create_config, REGISTRY as FC_REGISTRY
from mozregression.bisector import BisectRunner
from mozregression.launchers import REGISTRY as APP_REGISTRY
from mozregression.test_runner import ManualTestRunner, CommandTestRunner


def parse_args(argv=None):
    """
    Parse command line options.
    """
    usage = ("\n"
             " %(prog)s [OPTIONS]"
             " [[--bad BAD_DATE]|[--bad-release BAD_RELEASE]]"
             " [[--good GOOD_DATE]|[--good-release GOOD_RELEASE]]"
             "\n"
             " %(prog)s [OPTIONS]"
             " --inbound --bad-rev BAD_REV --good-rev GOOD_REV")

    parser = ArgumentParser(usage=usage)
    parser.add_argument("--version", action="version", version=__version__,
                        help=("print the mozregression version number and"
                              " exits."))

    parser.add_argument("-b", "--bad",
                        metavar="YYYY-MM-DD",
                        dest="bad_date",
                        help=("first known bad nightly build, default is"
                              " today."))

    parser.add_argument("-g", "--good",
                        metavar="YYYY-MM-DD",
                        dest="good_date",
                        help="last known good nightly build.")

    parser.add_argument("--list-releases",
                        action="store_true",
                        help="list all known releases and exit")

    parser.add_argument("--bad-release",
                        type=int,
                        help=("first known bad nightly build. This option"
                              " is incompatible with --bad."))

    parser.add_argument("--good-release",
                        type=int,
                        help=("last known good nightly build. This option is"
                              " incompatible with --good."))

    parser.add_argument("--inbound",
                        action="store_true",
                        help=("use inbound instead of nightlies (use"
                              " --good-rev and --bad-rev options."))

    parser.add_argument("--bad-rev", dest="first_bad_revision",
                        help=("first known bad revision (use with"
                              " --inbound)."))

    parser.add_argument("--good-rev", dest="last_good_revision",
                        help=("last known good revision (use with"
                              " --inbound)."))

    parser.add_argument("--find-fix", action="store_true",
                        help="Search for a bug fix instead of a regression.")

    parser.add_argument("-e", "--addon",
                        dest="addons",
                        action='append',
                        default=[],
                        metavar="PATH1",
                        help="addon to install; repeat for multiple addons.")

    parser.add_argument("-p", "--profile",
                        metavar="PATH",
                        help="profile to use with nightlies.")

    parser.add_argument("-a", "--arg",
                        dest="cmdargs",
                        action='append',
                        default=[],
                        metavar="ARG1",
                        help=("a command-line argument to pass to the"
                              " application; repeat for multiple arguments."))

    parser.add_argument("-n", "--app",
                        choices=FC_REGISTRY.names(),
                        default="firefox",
                        help="application name. Default: %(default)s.")

    parser.add_argument("--repo",
                        metavar="[mozilla-aurora|mozilla-beta|...]",
                        help="repository name used for nightly hunting.")

    parser.add_argument("--inbound-branch",
                        metavar="[b2g-inbound|fx-team|...]",
                        help="inbound branch name on ftp.mozilla.org.")

    parser.add_argument("--bits",
                        choices=("32", "64"),
                        default=mozinfo.bits,
                        help=("force 32 or 64 bit version (only applies to"
                              " x86_64 boxes). Default: %(default)s bits."))

    parser.add_argument("-c", "--command",
                        help=("Test command to evaluate builds automatically."
                              " A return code of 0 will evaluate build as"
                              " good, any other value will evaluate the build"
                              " as bad."))

    parser.add_argument("--persist",
                        help=("the directory in which downloaded files are"
                              " to persist."))

    parser.add_argument("--http-cache-dir",
                        help=("the directory for caching http requests."
                              " If not set there will be an in-memory cache"
                              " used."))
    parser.add_argument('--http-timeout', type=float, default=30.0,
                        help=("Timeout in seconds to abort requests when there"
                              " is no activity from the server. Default to"
                              " %(default)s seconds - increase this if you"
                              " are under a really slow network."))

    commandline.add_logging_group(parser)
    options = parser.parse_args(argv)
    options.bits = parse_bits(options.bits)
    return options


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


def cli(argv=None):
    """
    main entry point of mozregression command line.
    """
    options = parse_args(argv)
    logger = commandline.setup_logging("mozregression",
                                       options,
                                       {"mach": sys.stdout})

    if options.list_releases:
        print(formatted_valid_release_dates())
        sys.exit()

    cache_session = limitedfilecache.get_cache(
        options.http_cache_dir, limitedfilecache.ONE_GIGABYTE,
        logger=get_default_logger('Limited File Cache'))
    set_http_cache_session(cache_session,
                           get_defaults={"timeout": options.http_timeout})

    fetch_config = create_config(options.app, mozinfo.os, options.bits)

    if options.command is None:
        launcher_kwargs = dict(
            addons=options.addons,
            profile=options.profile,
            cmdargs=options.cmdargs,
        )
        test_runner = ManualTestRunner(fetch_config,
                                       persist=options.persist,
                                       launcher_kwargs=launcher_kwargs)
    else:
        test_runner = CommandTestRunner(fetch_config, options.command,
                                        persist=options.persist)

    runner = BisectRunner(fetch_config, test_runner, options)

    if fetch_config.is_inbound():
        # this can be useful for both inbound and nightly, because we
        # can go to inbound from nightly.
        fetch_config.set_inbound_branch(options.inbound_branch)

    if options.inbound:
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
        sys.exit("%s\n%s" % (exc, formatted_valid_release_dates()))
    except (MozRegressionError, RequestException) as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    cli()
