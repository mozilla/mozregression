# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
This module provides an API to integrate mozregression within mach.

Be careful to not break backward compatibility here, or you will
break mach!
"""

from argparse import Namespace

from mozregression.cli import create_parser
from mozregression.config import DEFAULT_CONF_FNAME, get_defaults
from mozregression.main import main, pypi_latest_version
from mozregression import __version__


def new_release_on_pypi():
    """
    Check if a new release is available on pypi and returns it.

    None is returned in case of error or if there is no new version.
    """
    try:
        pypi_version = pypi_latest_version()
    except Exception:
        return
    if pypi_version != __version__:
        return pypi_version


def parser():
    """
    Create and returns the mozregression ArgumentParser instance.
    """
    defaults = get_defaults(DEFAULT_CONF_FNAME)
    return create_parser(defaults=defaults)


def run(options):
    """
    Run mozregression given a dict of options.
    """
    main(namespace=Namespace(**options), check_new_version=False)
