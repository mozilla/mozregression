#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import sys
import re
import mozinfo
import datetime

from argparse import ArgumentParser
from ConfigParser import SafeConfigParser, Error
from mozlog.structured import commandline

from mozregression import __version__, errors
from mozregression.fetch_configs import REGISTRY as FC_REGISTRY

DEFAULT_CONF_FNAME = os.path.expanduser(os.path.join("~",
                                                     ".mozregression.cfg"))


def parse_date(date_string):
    """
    Returns a date from a string.
    """
    regex = re.compile(r'(\d{4})\-(\d{1,2})\-(\d{1,2})')
    matched = regex.match(date_string)
    if not matched:
        raise errors.DateFormatError(date_string)
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


def releases():
    """
    Provide the list of releases with their associated dates.

    The date is a string formated as "yyyy-mm-dd", and the release an integer.
    """
    # The dates comes from from https://wiki.mozilla.org/RapidRelease/Calendar,
    # using the ones in the "aurora" column. This is because the merge date for
    # aurora corresponds to the last nightly for that release. See bug 996812.
    return {
        5: "2011-04-12",
        6: "2011-05-24",
        7: "2011-07-05",
        8: "2011-08-16",
        9: "2011-09-27",
        10: "2011-11-08",
        11: "2011-12-20",
        12: "2012-01-31",
        13: "2012-03-13",
        14: "2012-04-24",
        15: "2012-06-05",
        16: "2012-07-16",
        17: "2012-08-27",
        18: "2012-10-08",
        19: "2012-11-19",
        20: "2013-01-07",
        21: "2013-02-19",
        22: "2013-04-01",
        23: "2013-05-13",
        24: "2013-06-24",
        25: "2013-08-05",
        26: "2013-09-16",
        27: "2013-10-28",
        28: "2013-12-09",
        29: "2014-02-03",
        30: "2014-03-17",
        31: "2014-04-28",
        32: "2014-06-09",
        33: "2014-07-21",
        34: "2014-09-02",
        35: "2014-10-13",
        36: "2014-11-28",
        37: "2015-01-12",
        38: "2015-02-23",
        39: "2015-03-30",
        40: "2015-05-11",
        41: "2015-06-29",
    }


def date_of_release(release):
    """
    Provide the date of a release.
    """
    try:
        return releases()[release]
    except KeyError:
        raise errors.UnavailableRelease(release)


def formatted_valid_release_dates():
    """
    Returns a formatted string (ready to be printed) representing
    the valid release dates.
    """
    message = "Valid releases: \n"
    for key, value in releases().iteritems():
        message += '% 3s: %s\n' % (key, value)

    return message


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
