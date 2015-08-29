# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Reading and writing of the configuration file.
"""

import os
import mozinfo

from configobj import ConfigObj, ParseError
try:
    import blessings
except ImportError:
    blessings = None

from mozregression.errors import MozRegressionError


CONFIG_FILE_HELP_URL = (
    "http://mozilla.github.io/mozregression/documentation/configuration.html"
)
DEFAULT_CONF_FNAME = os.path.expanduser(
    os.path.join("~", ".mozilla", "mozregression", "mozregression.cfg")
)


def get_defaults(conf_path):
    """
    Get custom defaults from configuration file in argument.
    """
    defaults = {}
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
          " can set NONE to not limit the persist dir, or any custom value"
          " you like." % default)
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
    term = blessings.Terminal() if blessings else None

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
        name = term.green(optname) if term else optname
        print "%s: %s" % (name, value)

    _set_option('persist', _get_persist_dir,
                os.path.join(conf_dir, "persist"))

    _set_option('persist-size-limit', _get_persist_size_limit, 20.0)

    if mozinfo.os != 'mac' and mozinfo.bits == 64:
        _set_option('bits', _get_bits, 64)

    config.write()

    conf_path_str = term.bold(conf_path) if term else conf_path
    print
    print "Config file ", conf_path_str, " written."
    print ("Note you can edit it manually, and there are other options you can"
           " configure. See %s." % CONFIG_FILE_HELP_URL)
