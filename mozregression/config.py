# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Reading and writing of the configuration file.
"""

import os
import mozinfo

from configobj import ConfigObj, ParseError

from mozregression.log import colorize
from mozregression.errors import MozRegressionError


CONFIG_FILE_HELP_URL = (
    "http://mozilla.github.io/mozregression/documentation/configuration.html"
)
DEFAULT_CONF_FNAME = os.path.expanduser(
    os.path.join("~", ".mozilla", "mozregression", "mozregression.cfg")
)
TC_CREDENTIALS_FNAME = os.path.expanduser(
    os.path.join("~", ".mozilla", "mozregression",
                 "taskcluster-credentials.json")
)
ARCHIVE_BASE_URL = "https://archive.mozilla.org/pub"
# when a bisection range needs to be expanded, the following value is used to
# specify how many builds we try (if 20, we will try 20 before the lower limit,
# and another 20 after the higher limit)
DEFAULT_EXPAND = 20

# default values when not defined in config file.
# Note that this is also the list of options that can be used in config file
DEFAULTS = {
    'build-type': 'opt',
    'persist': None,
    'profile': None,
    'repo': None,
    'inbound-branch': None,
    'bits': None,
    'profile-persistence': 'clone',
    'app': 'firefox',
    'persist-size-limit': 0,
    'http-timeout': 30.0,
    'no-background-dl': '',
    'background-dl-policy': 'cancel',
    'taskcluster-clientid': None,
    'taskcluster-accesstoken': None,
    'process-output': None,
    'mode': 'classic',
    'approx-policy': 'auto',
    'archive-base-url': ARCHIVE_BASE_URL,
}


def get_defaults(conf_path):
    """
    Get custom defaults from configuration file in argument.
    """
    defaults = dict(DEFAULTS)
    try:
        config = ConfigObj(conf_path)
    except ParseError, exc:
        raise MozRegressionError(
            "Error while reading the config file %s:\n  %s" % (conf_path, exc)
        )
    defaults.update(config)

    return defaults


def _get_persist_dir(default):
    print("You should configure a persist directory, where to put downloaded"
          " build files to reuse them in future bisections.")
    print("I recommend using %s. Leave blank to use that default. If you"
          " really don't want a persist dir type NONE, else you can"
          " just define a path that you would like to use." % default)
    value = raw_input("persist: ")
    if value == "NONE":
        return ''
    elif value:
        persist_dir = os.path.realpath(value)
    else:
        persist_dir = default

    if persist_dir:
        if not os.path.isdir(persist_dir):
            os.makedirs(persist_dir)
    return persist_dir


def _get_persist_size_limit(default):
    print("You should choose a size limit for the persist dir. I recommend you"
          " to use %s GiB, so leave it blank to use that default. Else you"
          " can type NONE to not limit the persist dir, or any number you like"
          " (a GiB value, so type 0.5 to allow ~500 MiB)." % default)
    value = raw_input('persist-size-limit: ')
    if value == "NONE":
        return 0.0
    elif value:
        return float(value)
    return default


def _get_bits(default):
    print("You are using a 64-bits system, so mozregression will by default"
          " use the 64 bits build files. If you want to change that to"
          " 32 bits by default, type 32 here.")
    while 1:
        value = raw_input('bits: ')
        if value in ('', '32', '64'):
            break
    if not value:
        return default
    return value


CONF_HELP = """\
# ------ mozregression configuration file ------

# Most of the command line options can be used in here.
# Just remove the -- from the long option names, e.g.

# bits = 32
# persist-size-limit = 15.0


"""


def write_conf(conf_path):
    conf_dir = os.path.dirname(conf_path)
    if not os.path.isdir(conf_dir):
        os.makedirs(conf_dir)

    config = ConfigObj(conf_path)
    if not config.initial_comment:
        config.initial_comment = CONF_HELP.splitlines()

    def _set_option(optname, getfunc, default):
        print
        if optname not in config:
            value = getfunc(default)
            if value is not None:
                config[optname] = value
            else:
                value = default
        else:
            print '%s already defined.' % optname
            value = config[optname]
        name = colorize("{fGREEN}%s{sRESET_ALL}" % optname)
        print "%s: %s" % (name, value)

    _set_option('persist', _get_persist_dir,
                os.path.join(conf_dir, "persist"))

    _set_option('persist-size-limit', _get_persist_size_limit, 20.0)

    if mozinfo.os != 'mac' and mozinfo.bits == 64:
        _set_option('bits', _get_bits, 64)

    config.write()

    print
    print colorize('Config file {sBRIGHT}%s{sRESET_ALL} written.' % conf_path)
    print("Note you can edit it manually, and there are other options you can"
          " configure. See %s." % CONFIG_FILE_HELP_URL)
