"""
This module provides an API to integrate mozregression within mach.

Be careful to not break backward compatibility here, or you will
break mach!
"""

from __future__ import absolute_import

from argparse import Namespace

from mozregression import __version__
from mozregression.cli import create_parser
from mozregression.config import DEFAULT_CONF_FNAME, get_config
from mozregression.main import main, pypi_latest_version


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
    defaults = get_config(DEFAULT_CONF_FNAME)
    return create_parser(defaults=defaults)


def run(options):
    """
    Run mozregression given a dict of options.
    """
    main(namespace=Namespace(**options), check_new_version=False, mozregression_variant="mach")
