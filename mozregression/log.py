"""
Logging and outputting configuration and utilities.
"""

import sys
import time

from colorama import Fore, Style
from mozlog.structuredlog import set_default_logger, StructuredLogger
from mozlog.handlers import StreamHandler, LogLevelFilter

ALLOW_COLOR = sys.stdout.isatty()


def _format_seconds(total):
    """Format number of seconds to MM:SS.DD form."""
    minutes, seconds = divmod(total, 60)
    return '%2d:%05.2f' % (minutes, seconds)


def init_logger(debug=True):
    start = time.time() * 1000
    level_color = {
        'WARNING': Fore.MAGENTA + Style.BRIGHT,
        'CRITICAL': Fore.RED + Style.BRIGHT,
        'ERROR': Fore.RED + Style.BRIGHT,
        'DEBUG': Fore.CYAN + Style.BRIGHT,
        'INFO':  Style.BRIGHT,
    }

    def format_log(data):
        level = data['level']
        elapsed = _format_seconds((data['time'] - start) / 1000)
        if ALLOW_COLOR:
            elapsed = Fore.BLUE + elapsed + Style.RESET_ALL
            if level in level_color:
                level = level_color[level] + level + Style.RESET_ALL
        return "%s %s: %s\n" % (elapsed, level, data['message'])

    logger = StructuredLogger("mozregression")
    handler = LogLevelFilter(StreamHandler(sys.stdout, format_log),
                             'debug' if debug else 'info')
    logger.add_handler(handler)

    set_default_logger(logger)
    return logger
