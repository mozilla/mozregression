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
import mozinfo
import datetime
import mozprofile
import re

from argparse import ArgumentParser, Action, SUPPRESS
from mozlog.structuredlog import get_default_logger

from mozregression import __version__
from mozregression.dates import to_datetime, parse_date, is_date_or_datetime
from mozregression.config import get_defaults, DEFAULT_CONF_FNAME, write_conf
from mozregression.tc_authenticate import tc_authenticate
from mozregression.fetch_configs import REGISTRY as FC_REGISTRY, create_config
from mozregression.errors import (MozRegressionError, DateFormatError,
                                  UnavailableRelease)
from mozregression.releases import (formatted_valid_release_dates,
                                    date_of_release)
from mozregression.log import init_logger, colorize


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


class ListBuildTypesAction(_StopAction):
    def __call__(self, parser, namespace, values, option_string=None):
        for name in FC_REGISTRY.names():
            print("%s:" % name)
            klass = FC_REGISTRY.get(name)
            for btype in klass.BUILD_TYPES:
                print("  %s" % btype.replace('-', ','))
        parser.exit()


def parse_args(argv=None, defaults=None):
    """
    Parse command line options.
    """
    parser = create_parser(defaults=defaults)
    return parser.parse_args(argv)


def create_parser(defaults):
    """
    Create the mozregression command line parser (ArgumentParser instance).
    """
    usage = ("\n"
             " %(prog)s [OPTIONS]"
             " [--bad DATE|BUILDID|RELEASE|CHANGESET]"
             " [--good DATE|BUILDID|RELEASE|CHANGESET]"
             "\n"
             " %(prog)s [OPTIONS] --launch DATE|BUILDID|RELEASE|CHANGESET"
             "\n"
             " %(prog)s --list-build-types"
             "\n"
             " %(prog)s --list-releases"
             "\n"
             " %(prog)s --write-conf")

    parser = ArgumentParser(usage=usage)
    parser.add_argument("--version", action="version", version=__version__,
                        help=("print the mozregression version number and"
                              " exits."))

    parser.add_argument("-b", "--bad",
                        metavar="DATE|BUILDID|RELEASE|CHANGESET",
                        help=("first known bad build, default is today."
                              " It can be a date (YYYY-MM-DD), a build id,"
                              " a release number or a changeset. If it is"
                              " a changeset, the default branch will be the"
                              " integration branch of the application"
                              " (e.g. mozilla-inbound for firefox), else"
                              " the default release branch for the application"
                              " will be used as the default (e.g"
                              " mozilla-central for firefox)."))

    parser.add_argument("-g", "--good",
                        metavar="DATE|BUILDID|RELEASE|CHANGESET",
                        help=("last known good build. Same possible values"
                              " as the --bad option."))

    parser.add_argument("--list-releases",
                        action=ListReleasesAction,
                        help="list all known releases and exit")

    parser.add_argument("-B", "--build-type",
                        default=defaults["build-type"],
                        help=("Build flavor - should be a comma separated list"
                              " of build options. Note that on nightly, only"
                              " opt is available most of the time. See"
                              " --list-build-types to see available values"
                              ". Defaults to %(default)s."))

    parser.add_argument("--list-build-types", action=ListBuildTypesAction,
                        help="List available build types combinations.")

    parser.add_argument("--find-fix", action="store_true",
                        help="Search for a bug fix instead of a regression.")

    parser.add_argument("-e", "--addon",
                        dest="addons",
                        action='append',
                        default=[],
                        metavar="PATH1",
                        help="addon to install; repeat for multiple addons.")

    parser.add_argument("-p", "--profile",
                        default=defaults["profile"],
                        metavar="PATH",
                        help="profile to use with nightlies.")

    parser.add_argument('--profile-persistence',
                        choices=('clone', 'clone-first', 'reuse'),
                        default=defaults["profile-persistence"],
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
                        default=defaults["app"],
                        help="application name. Default: %(default)s.")

    parser.add_argument("--repo",
                        metavar="[mozilla-aurora|mozilla-inbound|autoland...]",
                        default=defaults["repo"],
                        help="repository name used for the bisection.")

    parser.add_argument("--bits",
                        choices=("32", "64"),
                        default=defaults["bits"],
                        help=("force 32 or 64 bit version (only applies to"
                              " x86_64 boxes). Default: %s bits."
                              % defaults["bits"] or mozinfo.bits))

    parser.add_argument("-c", "--command",
                        help=("Test command to evaluate builds automatically."
                              " A return code of 0 will evaluate build as"
                              " good, any other value will evaluate the build"
                              " as bad."))

    parser.add_argument("--persist",
                        default=defaults["persist"],
                        help=("the directory in which downloaded files are"
                              " to persist. Defaults to %(default)r."))

    parser.add_argument('--persist-size-limit', type=float,
                        default=defaults['persist-size-limit'],
                        help=("Size limit for the persist directory in"
                              " gigabytes (GiB). When the limit is reached,"
                              " old builds are removed. 0 means no limit. Note"
                              " that at least 5 build files are kept,"
                              " regardless of this value."
                              " Defaults to %(default)s."))

    parser.add_argument('--http-timeout', type=float,
                        default=float(defaults['http-timeout']),
                        help=("Timeout in seconds to abort requests when there"
                              " is no activity from the server. Default to"
                              " %(default)s seconds - increase this if you"
                              " are under a really slow network."))

    parser.add_argument('--no-background-dl', action='store_false',
                        dest="background_dl",
                        default=(defaults['no-background-dl'].lower()
                                 not in ('1', 'yes', 'true')),
                        help=("Do not download next builds in the background"
                              " while evaluating the current build."))

    parser.add_argument('--background-dl-policy', choices=('cancel', 'keep'),
                        default=defaults['background-dl-policy'],
                        help=('Policy to use for background downloads.'
                              ' Possible values are "cancel" to cancel all'
                              ' pending background downloads or "keep" to keep'
                              ' downloading them when persist mode is enabled.'
                              ' The default is %(default)s.'))

    parser.add_argument('--approx-policy', choices=('auto', 'none'),
                        default=defaults['approx-policy'],
                        help=("Policy to reuse approximate persistent builds"
                              " instead of downloading the accurate ones."
                              " When auto, mozregression will try its best to"
                              " reuse the files, meaning that for 7 days of"
                              " bisection range it will try to reuse a build"
                              " which date approximates the build to download"
                              " by one day (before or after). Use none to"
                              " disable this behavior."
                              " Defaults to %(default)s."))

    parser.add_argument('--launch',
                        metavar="DATE|BUILDID|RELEASE|CHANGESET",
                        help=("Launch only one specific build. Same possible"
                              " values as the --bad option."))

    parser.add_argument('-P', '--process-output', choices=('none', 'stdout'),
                        default=defaults['process-output'],
                        help=("Manage process output logging. Set to stdout by"
                              " default when the build type is not 'opt'."))

    parser.add_argument('-M', '--mode', choices=('classic', 'no-first-check'),
                        default=defaults['mode'],
                        help=("bisection mode. 'classic' will check for the"
                              " first good and bad builds to really be good"
                              " and bad, and 'no-first-check' won't. Defaults"
                              " to %(default)s."))

    parser.add_argument('--archive-base-url',
                        default=defaults['archive-base-url'],
                        help=("Base url used to find the archived builds."
                              " Defaults to %(default)s"))

    parser.add_argument('--write-config',
                        action=WriteConfigAction,
                        help="Helps to write the configuration file.")

    parser.add_argument('--debug', '-d', action='store_true',
                        help='Show the debug output.')

    return parser


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


def get_default_date_range(fetch_config):
    """
    Compute the default date range (first, last) to bisect.
    """
    last_date = datetime.date.today()
    if fetch_config.app_name == 'jsshell':
        if fetch_config.os == "win" and fetch_config.bits == 64:
            first_date = datetime.date(2014, 5, 27)
        elif fetch_config.os == "linux" and "asan" in fetch_config.build_type:
            first_date = datetime.date(2013, 9, 1)
        else:
            first_date = datetime.date(2012, 4, 18)
    elif fetch_config.os == 'win' and fetch_config.bits == 64:
        # first firefox build date for win64 is 2010-05-28
        first_date = datetime.date(2010, 5, 28)
    else:
        first_date = datetime.date(2009, 1, 1)

    return first_date, last_date


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
        self.logger = init_logger(debug=options.debug)
        # allow to filter process output based on the user option
        if options.process_output is None:
            # process_output not user defined
            log_process_output = options.build_type != 'opt'
        else:
            log_process_output = options.process_output == 'stdout'
        get_default_logger("process").component_filter = \
            lambda data: data if log_process_output else None

        # filter some mozversion log lines
        re_ignore_mozversion_line = re.compile(
            r"^(platform_.+|application_vendor|application_remotingname"
            r"|application_id|application_display_name): .+"
        )
        get_default_logger("mozversion").component_filter = lambda data: (
            None if re_ignore_mozversion_line.match(data['message']) else data
        )

        self.action = None
        self.fetch_config = None

    def _convert_to_bisect_arg(self, value):
        """
        Transform a string value to a date or datetime if it looks like it.
        """
        try:
            value = parse_date(value)
        except DateFormatError:
            try:
                new_value = parse_date(date_of_release(value))
                self.logger.info("Using date %s for release %s"
                                 % (new_value, value))
                value = new_value
            except UnavailableRelease:
                self.logger.info("%s is not a release, assuming it's a hash..." % value)
        return value

    def validate(self):
        """
        Validate the options, define the `action` and `fetch_config` that
        should be used to run the application.
        """
        options = self.options

        user_defined_bits = options.bits is not None
        options.bits = parse_bits(options.bits or mozinfo.bits)
        fetch_config = create_config(options.app, mozinfo.os, options.bits)
        try:
            fetch_config.set_build_type(options.build_type)
        except MozRegressionError as msg:
            self.logger.warning(
                "%s (Defaulting to %r)" % (msg, fetch_config.build_type)
            )
        self.fetch_config = fetch_config

        fetch_config.set_repo(options.repo)
        if fetch_config.is_nightly():
            fetch_config.set_base_url(options.archive_base_url)

        if not user_defined_bits and \
                options.bits == 64 and \
                mozinfo.os == 'win' and \
                32 in fetch_config.available_bits():
            # inform users on windows that we are using 64 bit builds.
            self.logger.info("bits option not specified, using 64-bit builds.")

        if options.bits == 32 and mozinfo.os == 'mac':
            self.logger.info("only 64-bit builds available for mac, using "
                             "64-bit builds")

        if fetch_config.is_inbound() and fetch_config.tk_needs_auth():
            creds = tc_authenticate(self.logger)
            fetch_config.set_tk_credentials(creds)

        # set action for just use changset or data to bisect
        if options.launch:
            options.launch = self._convert_to_bisect_arg(options.launch)
            self.action = "launch_inbound"
            if is_date_or_datetime(options.launch) and \
                    not fetch_config.should_use_taskcluster():
                self.action = "launch_nightlies"
        else:
            # define good/bad default values if required
            default_good_date, default_bad_date = \
                get_default_date_range(fetch_config)
            if options.find_fix:
                default_bad_date, default_good_date = \
                    default_good_date, default_bad_date
            if not options.bad:
                options.bad = default_bad_date
                self.logger.info("No 'bad' option specified, using %s"
                                 % options.bad)
            else:
                options.bad = self._convert_to_bisect_arg(options.bad)
            if not options.good:
                options.good = default_good_date
                self.logger.info("No 'good' option specified, using %s"
                                 % options.good)
            else:
                options.good = self._convert_to_bisect_arg(options.good)

            self.action = "bisect_inbounds"
            if is_date_or_datetime(options.good) and \
                    is_date_or_datetime(options.bad):
                if not options.find_fix and \
                        to_datetime(options.good) > to_datetime(options.bad):
                    raise MozRegressionError(
                        ("Good date %s is later than bad date %s."
                         " Maybe you wanted to use the --find-fix"
                         " flag?") % (options.good, options.bad))
                elif options.find_fix and \
                        to_datetime(options.good) < to_datetime(options.bad):
                    raise MozRegressionError(
                        ("Bad date %s is later than good date %s."
                         " You should not use the --find-fix flag"
                         " in this case...") % (options.bad, options.good))
                if not fetch_config.should_use_taskcluster():
                    self.action = "bisect_nightlies"
        if self.action in ('launch_inbound', 'bisect_inbounds')\
                and not fetch_config.is_inbound():
            raise MozRegressionError('Unable to bisect inbound for `%s`'
                                     % fetch_config.app_name)
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
        defaults = get_defaults(conf_file)
        options = parse_args(argv=argv, defaults=defaults)
    if conf_file and not os.path.isfile(conf_file):
        print '*' * 10
        print colorize("You should use a config file. Please use the " +
                       '{sBRIGHT}--write-config{sRESET_ALL}' +
                       " command line flag to help you create one.")
        print '*' * 10
        print
    return Configuration(options)
