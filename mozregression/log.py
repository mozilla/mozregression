"""
Logging and outputting configuration and utilities.
"""

import sys
import time
import mozinfo

from colorama import Fore, Style, Back
from mozlog.structuredlog import set_default_logger, StructuredLogger
from mozlog.handlers import StreamHandler, LogLevelFilter

ALLOW_COLOR = sys.stdout.isatty()


def _format_seconds(total):
    """Format number of seconds to MM:SS.DD form."""
    minutes, seconds = divmod(total, 60)
    return '%2d:%05.2f' % (minutes, seconds)


def init_logger(debug=True, allow_color=ALLOW_COLOR, output=None):
    """
    Initialize the mozlog logger. Must be called once before using logs.
    """
    # late binding of sys.stdout is required for windows color to work
    output = output or sys.stdout
    start = time.time() * 1000
    level_color = {
        'WARNING': Fore.MAGENTA + Style.BRIGHT,
        'CRITICAL': Fore.RED + Style.BRIGHT,
        'ERROR': Fore.RED + Style.BRIGHT,
        'DEBUG': Fore.CYAN + Style.BRIGHT,
        'INFO': Style.BRIGHT,
    }
    time_color = Fore.BLUE
    if mozinfo.os == "win":
        time_color += Style.BRIGHT  # this is unreadable on windows without it

    def format_log(data):
        level = data['level']
        elapsed = _format_seconds((data['time'] - start) / 1000)
        if allow_color:
            elapsed = time_color + elapsed + Style.RESET_ALL
            if level in level_color:
                level = level_color[level] + level + Style.RESET_ALL
        return "%s %s: %s\n" % (elapsed, level, data['message'])

    logger = StructuredLogger("mozregression")
    handler = LogLevelFilter(StreamHandler(output, format_log),
                             'debug' if debug else 'info')
    logger.add_handler(handler)

    set_default_logger(logger)
    return logger


COLORS = {}
NO_COLORS = {}

for prefix, st in (('b', Back), ('s', Style), ('f', Fore)):
    for name, value in st.__dict__.iteritems():
        COLORS[prefix + name] = value
        NO_COLORS[prefix + name] = ''


def colorize(text, allow_color=ALLOW_COLOR):
    """
    *colorize* text to be displayed on terminal.

    You can pass a string with key parameters to be formatted. you can use
    every name available from colorama.{Back,Style,Fore}, with corresponding
    prefixes, followed by the property you want to use. Prefixes are:

    - Back: "b"
    - Style: "s"
    - Fore: "f"

    Example::

    >> colorize("{fRED}hellow{sRESET_ALL}")

    Will colorize the text on the screen if allow_color is True (equivalent to
    Fore.RED + "hello" + Style.RESET_ALL).
    If allow_color is False, no color special char will be added, thus the
    returned text will be "hello".
    """
    data = COLORS if allow_color else NO_COLORS
    return text.format(**data)
