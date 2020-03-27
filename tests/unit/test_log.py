from __future__ import absolute_import

import re

import pytest
from colorama import Fore, Style
from six import StringIO

from mozregression import log


def init_logger(mocker, **kwargs):
    stream = StringIO()
    kwargs["output"] = stream
    mocker.patch("mozregression.log.set_default_logger")
    return log.init_logger(**kwargs), stream


def test_logger_without_color(mocker):
    logger, stream = init_logger(mocker, allow_color=False)
    logger.error("argh")
    assert "ERROR: argh" in stream.getvalue()


def test_logger_with_color(mocker):
    logger, stream = init_logger(mocker, allow_color=True)
    logger.error("argh")
    assert re.search(".+ERROR.+: argh", stream.getvalue())


@pytest.mark.parametrize("debug", [False, True])
def test_logger_debug(mocker, debug):
    logger, stream = init_logger(mocker, allow_color=False, debug=debug)
    logger.info("info")
    logger.debug("debug")
    data = stream.getvalue()
    assert "info" in data
    if debug:
        assert "debug" in data
    else:
        assert "debug" not in data


def test_colorize():
    assert log.colorize("stuff", allow_color=True) == "stuff"
    assert log.colorize("{fRED}stuff{sRESET_ALL}", allow_color=True) == (
        Fore.RED + "stuff" + Style.RESET_ALL
    )
    assert log.colorize("{fRED}stuf{sRESET_ALL}", allow_color=False) == "stuf"
