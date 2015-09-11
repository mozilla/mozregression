import sys
import logging
from colorlog import ColoredFormatter


def setup_logging(log_level="info"):
    logging.basicConfig(level=logging.DEBUG
                        if log_level == "debug" else logging.INFO)
    # global formatter
    logging.getLogger().handlers[0].setFormatter(ColoredFormatter(
        "%(log_color)s%(levelname)-8s%(reset)s [%(name)s] %(message)s"
    ))
    # mozregression formatter (do not include the logger name)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColoredFormatter(
        "%(log_color)s%(levelname)-8s%(reset)s %(message)s"
    ))
    mlog = logging.getLogger('mozregression')
    mlog.addHandler(handler)
    mlog.propagate = False

    logging.getLogger("mozversion").setLevel(logging.ERROR)
    logging.getLogger("requests").setLevel(logging.ERROR)
    logging.getLogger("redo").setLevel(logging.INFO)
    logging.getLogger("taskcluster").setLevel(logging.ERROR)
