import time
from multiprocessing import Process
from pathlib import Path

from glean import Configuration, Glean, load_metrics, load_pings
from mozlog import get_proxy_logger
from pkg_resources import resource_filename

from mozregression import __version__

LOG = get_proxy_logger("telemetry")
PINGS = load_pings(resource_filename(__name__, "pings.yaml"))
METRICS = load_metrics(resource_filename(__name__, "metrics.yaml"))


def initialize_telemetry(upload_enabled):
    mozregression_path = Path.home() / ".mozilla" / "mozregression"
    Glean.initialize(
        application_id="org.mozilla.mozregression",
        application_version=__version__,
        upload_enabled=upload_enabled,
        configuration=Configuration(allow_multiprocessing=False),
        data_dir=mozregression_path / "data",
    )


def _send_telemetry_ping(variant, appname):
    METRICS.usage.variant.set(variant)
    METRICS.usage.app.set(appname)
    PINGS.usage.submit()


def send_telemetry_ping(variant, appname):
    _send_telemetry_ping(variant, appname)


def send_telemetry_ping_oop(variant, appname, upload_enabled):
    """
    This somewhat convoluted function forks off a process (using
    Python's multiprocessing module) and sends a glean ping --
    this is to get around the fact that we sometimes might
    call mozregression inside a process which is itself using
    Glean for other purposes (e.g. mach)
    """

    def _send_telemetry_ping_oop(variant, appname, upload_enabled):
        initialize_telemetry(upload_enabled)
        if upload_enabled:
            _send_telemetry_ping(variant, appname)
            # we sleep to give glean's async machinery a chance to
            # submit the ping
            time.sleep(1)

    p = Process(target=_send_telemetry_ping_oop, args=(variant, appname, upload_enabled))
    p.start()
