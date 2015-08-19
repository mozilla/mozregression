#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from argparse import ArgumentParser
from ConfigParser import SafeConfigParser, Error
from mozlog.structured import commandline

import os
import sys

from mozregression import __version__
from mozregression.fetch_configs import REGISTRY as FC_REGISTRY

DEFAULT_CONF_FNAME = os.path.expanduser(os.path.join("~",
                                                     ".mozregression.cfg"))


def get_defaults(conf_name):
    """
    Get custom defaults from configuration file in argument
    """
    defaults = {}

    if os.path.isfile(conf_name):
        try:
            config = SafeConfigParser()
            config.read([conf_name])
            defaults = dict(config.items("Defaults"))
            print("%s loaded" % conf_name)
        except Error as err:
            sys.exit("Error while parsing %s =>  no custom default values\n%s"
                     % (conf_name, str(err)))

    return defaults


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
             " --bad-rev BAD_REV --good-rev GOOD_REV")

    defaults = get_defaults(DEFAULT_CONF_FNAME)
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

    parser.add_argument("-a", "--arg",
                        dest="cmdargs",
                        action='append',
                        default=[],
                        metavar="ARG1",
                        help=("a command-line argument to pass to the"
                              " application; repeat for multiple arguments."))

    parser.add_argument('--pref', nargs='*', dest='prefs',
                        help=(" A preference to set. Must be a key-value pair"
                              " separated by a ':'"))

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
                              " to persist."))

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

    commandline.add_logging_group(
        parser,
        include_formatters=commandline.TEXT_FORMATTERS
    )
    options = parser.parse_args(argv)
    return options
