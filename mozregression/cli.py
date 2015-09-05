#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
This module parses and checks the command line with :func:`cli` and return a
:class:`Configuration` object that hold information for running the
application.

:func:`cli` is intended to be the only public interface of this module.
"""

import os
import sys
import re
import mozinfo
import datetime
import mozprofile

from argparse import ArgumentParser, Action, SUPPRESS
from mozlog.structured import commandline
try:
    import blessings
except ImportError:
    blessings = None

from mozregression import __version__
from mozregression.config import get_defaults, DEFAULT_CONF_FNAME, write_conf
from mozregression.fetch_configs import REGISTRY as FC_REGISTRY, create_config
from mozregression.errors import MozRegressionError, DateFormatError
from mozregression.releases import (formatted_valid_release_dates,
                                    date_of_release)


class _StopAction(Action):
    def __init__(self, option_strings, dest=SUPPRESS, default=SUPPRESS,
                 help=None):
        super(_StopAction, self).__init__(option_strings=option_strings,
                                          dest=dest, default=default,
                                          nargs=0, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        raise NotImplementedError


class ListReleasesAction(_StopAction):
    def __call__(self, parser, namespace, values, option_string=None):
        print(formatted_valid_release_dates())
        parser.exit()


class WriteConfigAction(_StopAction):
    def __call__(self, parser, namespace, values, option_string=None):
        write_conf(DEFAULT_CONF_FNAME)
        parser.exit()


def parse_args(argv=None, defaults=None):
    """
    Parse command line options.
    """
    parser = create_parser(defaults=defaults)
    return parser.parse_args(argv)


def create_parser(defaults=None):
    """
    Create the mozregression command line parser (ArgumentParser instance).
    """
    usage = ("\n"
             " %(prog)s [OPTIONS]"
             " [[--bad BAD_DATE]|[--bad-release BAD_RELEASE]]"
             " [[--good GOOD_DATE]|[--good-release GOOD_RELEASE]]"
             "\n"
             " %(prog)s [OPTIONS]"
             " --bad-rev BAD_REV --good-rev GOOD_REV"
             "\n"
             " %(prog)s [OPTIONS] --launch DATE_OR_REV"
             "\n"
             " %(prog)s --list-releases"
             "\n"
             " %(prog)s --write-conf")

    defaults = defaults or {}
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
                        action=ListReleasesAction,
                        help="list all known releases and exit")

    parser.add_argument("--bad-release",
                        type=int,
                        help=("first known bad nightly build. This option"
                              " is incompatible with --bad."))

    parser.add_argument("--good-release",
                        type=int,
                        help=("last known good nightly build. This option is"
                              " incompatible with --good."))

    parser.add_argument("--bad-rev", dest="first_bad_revision",
                        help=("first known bad revision (for inbound"
                              " bisection)."))

    parser.add_argument("--good-rev", dest="last_good_revision",
                        help=("last known good revision (for inbound"
                              " bisection)."))

    parser.add_argument("--find-fix", action="store_true",
                        help="Search for a bug fix instead of a regression.")

    parser.add_argument("-e", "--addon",
                        dest="addons",
                        action='append',
                        default=[],
                        metavar="PATH1",
                        help="addon to install; repeat for multiple addons.")

    parser.add_argument("-p", "--profile",
                        default=defaults.get("profile"),
                        metavar="PATH",
                        help="profile to use with nightlies.")

    parser.add_argument('--profile-persistence',
                        choices=('clone', 'clone-first', 'reuse'),
                        default=defaults.get("profile-persistence", 'clone'),
                        help=("Persistence of the used profile. Before"
                              " each tested build, a profile is used. If"
                              " the value of this option is 'clone', each"
                              " test uses a fresh clone. If the value is"
                              " 'clone-first', the profile is cloned once"
                              " then reused for all builds during the "
                              " bisection. If the value is 'reuse', the given"
                              " profile is directly used. Note that the"
                              " profile might be modified by mozregression."
                              " Defaults to %(default)s."))

    parser.add_argument("-a", "--arg",
                        dest="cmdargs",
                        action='append',
                        default=[],
                        metavar="ARG1",
                        help=("a command-line argument to pass to the"
                              " application; repeat for multiple arguments."))

    parser.add_argument('--pref', nargs='*', dest='prefs',
                        help=(" A preference to set. Must be a key-value pair"
                              " separated by a ':'. Note that if your"
                              " preference is of type float, you should"
                              " pass it as a string, e.g.:"
                              " --pref \"layers.low-precision-opacity:'0.0'\""
                              ))

    parser.add_argument('--preferences', nargs="*", dest='prefs_files',
                        help=("read preferences from a JSON or INI file. For"
                              " INI, use 'file.ini:section' to specify a"
                              " particular section."))

    parser.add_argument("-n", "--app",
                        choices=FC_REGISTRY.names(),
                        default=defaults.get("app", "firefox"),
                        help="application name. Default: %(default)s.")

    parser.add_argument("--repo",
                        metavar="[mozilla-aurora|mozilla-beta|...]",
                        default=defaults.get("repo"),
                        help="repository name used for nightly hunting.")

    parser.add_argument("--inbound-branch",
                        metavar="[b2g-inbound|fx-team|...]",
                        default=defaults.get("inbound-branch"),
                        help="inbound branch name on archive.mozilla.org.")

    parser.add_argument("--bits",
                        choices=("32", "64"),
                        default=defaults.get("bits"),
                        help=("force 32 or 64 bit version (only applies to"
                              " x86_64 boxes). Default: %(default)s bits."))

    parser.add_argument("-c", "--command",
                        help=("Test command to evaluate builds automatically."
                              " A return code of 0 will evaluate build as"
                              " good, any other value will evaluate the build"
                              " as bad."))

    parser.add_argument("--persist",
                        default=defaults.get("persist"),
                        help=("the directory in which downloaded files are"
                              " to persist. Defaults to %(default)r."))

    parser.add_argument('--persist-size-limit', type=float,
                        default=defaults.get('persist-size-limit', 0),
                        help=("Size limit for the persist directory in"
                              " gigabytes (GiB). When the limit is reached,"
                              " old builds are removed. 0 means no limit. Note"
                              " that at least 5 build files are kept,"
                              " regardless of this value."
                              " Defaults to %(default)s."))

    parser.add_argument('--http-timeout', type=float,
                        default=float(defaults.get("http-timeout", 30.0)),
                        help=("Timeout in seconds to abort requests when there"
                              " is no activity from the server. Default to"
                              " %(default)s seconds - increase this if you"
                              " are under a really slow network."))

    parser.add_argument('--no-background-dl', action='store_false',
                        dest="background_dl",
                        default=(defaults.get('no-background-dl', '').lower()
                                 not in ('1', 'yes', 'true')),
                        help=("Do not download next builds in the background"
                              " while evaluating the current build."))

    parser.add_argument('--background-dl-policy', choices=('cancel', 'keep'),
                        default=defaults.get('background-dl-policy', 'cancel'),
                        help=('Policy to use for background downloads.'
                              ' Possible values are "cancel" to cancel all'
                              ' pending background downloads or "keep" to keep'
                              ' downloading them when persist mode is enabled.'
                              ' The default is %(default)s.'))

    parser.add_argument('--launch',
                        metavar="DATE_OR_REV",
                        help="Launch only one specific build by date (nightly)"
                             " or changeset (inbound).")

    parser.add_argument('--write-config',
                        action=WriteConfigAction,
                        help="Helps to write the configuration file.")

    commandline.add_logging_group(
        parser,
        include_formatters=commandline.TEXT_FORMATTERS
    )
    return parser


def parse_date(date_string):
    """
    Returns a date from a string.
    """
    regex = re.compile(r'(\d{4})\-(\d{1,2})\-(\d{1,2})')
    matched = regex.match(date_string)
    if not matched:
        raise DateFormatError(date_string)
    return datetime.date(int(matched.group(1)),
                         int(matched.group(2)),
                         int(matched.group(3)))


def parse_bits(option_bits):
    """
    Returns the correctly typed bits.
    """
    if option_bits == "32":
        return 32
    else:
        # if 64 bits is passed on a 32 bit system, it won't be honored
        return mozinfo.bits


def preferences(prefs_files, prefs_args):
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


def check_nightlies(options, fetch_config, logger):
    default_bad_date = str(datetime.date.today())
    default_good_date = "2009-01-01"
    if mozinfo.os == 'win' and options.bits == 64:
        # first firefox build date for win64 is 2010-05-28
        default_good_date = "2010-05-28"
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
        raise MozRegressionError("Options '--bad-release' and '--bad'"
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
        raise MozRegressionError("Options '--good-release' and '--good'"
                                 " are incompatible.")
    elif options.good_release:
        options.good_date = date_of_release(options.good_release)
        logger.info("Using 'good' date %s for release %s"
                    % (options.good_date, options.good_release))

    options.good_date = good_date = parse_date(options.good_date)
    options.bad_date = bad_date = parse_date(options.bad_date)
    if good_date > bad_date and not options.find_fix:
        raise MozRegressionError(("Good date %s is later than bad date %s."
                                  " Maybe you wanted to use the --find-fix"
                                  " flag ?") % (good_date, bad_date))
    elif good_date < bad_date and options.find_fix:
        raise MozRegressionError(("Bad date %s is later than good date %s."
                                  " You should not use the --find-fix flag"
                                  " in this case...") % (bad_date, good_date))


def check_inbounds(options, fetch_config, logger):
    if not fetch_config.is_inbound():
        raise MozRegressionError('Unable to bisect inbound for `%s`'
                                 % fetch_config.app_name)
    if not options.last_good_revision or not options.first_bad_revision:
        raise MozRegressionError("If bisecting inbound, both --good-rev"
                                 " and --bad-rev must be set")


class Configuration(object):
    """
    Holds the configuration extracted from the command line.

    This is usually instantiated by calling :func:`cli`.

    The constructor only initializes the `logger`.

    The configuration should not be used (except for the logger attribute)
    until :meth:`validate` is called.

    :attr logger: the mozlog logger, created using the command line options
    :attr options: the raw command line options
    :attr action: the action that the user want to do. This is a string
                  ("bisect_inbounds" or "bisect_nightlies")
    :attr fetch_config: the fetch_config instance, required to find
                        information about a build
    """
    def __init__(self, options):
        self.options = options
        self.logger = commandline.setup_logging("mozregression",
                                                self.options,
                                                {"mach": sys.stdout})
        self.action = None
        self.fetch_config = None

    def validate(self):
        """
        Validate the options, define the `action` and `fetch_config` that
        should be used to run the application.
        """
        options = self.options

        if not options.persist:
            # expicitely set None since we have code that rely on that
            # TODO address this.
            options.persist = None

        user_defined_bits = options.bits is not None
        options.bits = parse_bits(options.bits or mozinfo.bits)
        fetch_config = create_config(options.app, mozinfo.os, options.bits)
        self.fetch_config = fetch_config

        if not user_defined_bits and \
                options.bits == 64 and \
                mozinfo.os == 'win' and \
                32 in fetch_config.available_bits():
            # inform users on windows that we are using 64 bit builds.
            self.logger.info("bits option not specified, using 64-bit builds.")

        if fetch_config.is_inbound():
            # this can be useful for both inbound and nightly, because we
            # can go to inbound from nightly.
            fetch_config.set_inbound_branch(options.inbound_branch)
        # set action for just use changset or data to bisect
        if options.launch:
            try:
                options.launch = parse_date(options.launch)
                self.action = "launch_nightlies"
            except DateFormatError:
                self.action = "launch_inbound"

        # bisect inbound if last good revision or first bad revision are set
        elif options.first_bad_revision or options.last_good_revision:
            self.action = "bisect_inbounds"
            check_inbounds(options, fetch_config, self.logger)
        else:
            self.action = "bisect_nightlies"
            check_nightlies(options, fetch_config, self.logger)

        options.preferences = preferences(options.prefs_files, options.prefs)
        # convert GiB to bytes.
        options.persist_size_limit = \
            int(abs(float(options.persist_size_limit)) * 1073741824)


def cli(argv=None, conf_file=DEFAULT_CONF_FNAME, namespace=None):
    """
    parse cli args basically and returns a :class:`Configuration`.

    if namespace is given, it will be used as a arg parsing result, so no
    arg parsing will be done.
    """
    if namespace:
        options = namespace
    else:
        defaults = None
        if conf_file:
            defaults = get_defaults(conf_file)
        options = parse_args(argv=argv, defaults=defaults)
    if conf_file and not os.path.isfile(conf_file):
        term = blessings.Terminal() if blessings else None
        print '*' * ((term and term.width) or 10)
        print ("You should use a config file. Please use the " +
               (term.bold('--write-config') if term else '--write-config') +
               " command line flag to help you create one.")
        print '*' * ((term and term.width) or 10)
        print
    return Configuration(options)
