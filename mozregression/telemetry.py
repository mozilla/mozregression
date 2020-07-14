from collections import namedtuple
from multiprocessing import Process
from pathlib import Path

from glean import Configuration, Glean, load_metrics, load_pings
from mozlog import get_proxy_logger
from pkg_resources import resource_filename

from mozregression import __version__
from mozregression.dates import is_date_or_datetime, to_datetime

LOG = get_proxy_logger("telemetry")
PINGS = load_pings(resource_filename(__name__, "pings.yaml"))
METRICS = load_metrics(resource_filename(__name__, "metrics.yaml"))

UsageMetrics = namedtuple(
    "UsageMetrics", ["variant", "appname", "build_type", "good", "bad", "launch"]
)


def initialize_telemetry(upload_enabled, allow_multiprocessing=False):
    mozregression_path = Path.home() / ".mozilla" / "mozregression"
    Glean.initialize(
        application_id="org.mozilla.mozregression",
        application_version=__version__,
        upload_enabled=upload_enabled,
        configuration=Configuration(allow_multiprocessing=allow_multiprocessing),
        data_dir=mozregression_path / "data",
    )


def _send_telemetry_ping(metrics):
    METRICS.usage.variant.set(metrics.variant)
    METRICS.usage.app.set(metrics.appname)
    METRICS.usage.build_type.set(metrics.build_type)
    if is_date_or_datetime(metrics.good):
        METRICS.usage.good_date.set(to_datetime(metrics.good))
    if is_date_or_datetime(metrics.bad):
        METRICS.usage.bad_date.set(to_datetime(metrics.bad))
    if is_date_or_datetime(metrics.launch):
        METRICS.usage.launch_date.set(to_datetime(metrics.launch))
    PINGS.usage.submit()


def send_telemetry_ping(metrics):
    LOG.debug("Sending usage ping")
    _send_telemetry_ping(metrics)


def _send_telemetry_ping_oop(metrics, upload_enabled):
    initialize_telemetry(upload_enabled, allow_multiprocessing=True)
    if upload_enabled:
        _send_telemetry_ping(metrics)


def send_telemetry_ping_oop(metrics, upload_enabled):
    """
    This somewhat convoluted function forks off a process (using
    Python's multiprocessing module) and sends a glean ping --
    this is to get around the fact that we sometimes might
    call mozregression inside a process which is itself using
    Glean for other purposes (e.g. mach)
    """
    LOG.debug("Sending usage ping (OOP)")
    p = Process(target=_send_telemetry_ping_oop, args=(metrics, upload_enabled))
    p.start()
