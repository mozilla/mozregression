import platform
from collections import namedtuple
from multiprocessing import Process
from pathlib import Path

import distro
import importlib_resources
import mozinfo
from glean import Configuration, Glean, load_metrics, load_pings
from mozlog import get_proxy_logger

from mozregression import __version__
from mozregression.dates import is_date_or_datetime, to_datetime

LOG = get_proxy_logger("telemetry")

PINGS = load_pings(importlib_resources.files(__name__) / "pings.yaml")
METRICS = load_metrics(importlib_resources.files(__name__) / "metrics.yaml")

UsageMetrics = namedtuple(
    "UsageMetrics",
    [
        "variant",
        "appname",
        "build_type",
        "good",
        "bad",
        "launch",
        "windows_version",
        "mac_version",
        "linux_version",
        "linux_distro",
        "python_version",
    ],
)


def get_system_info():
    """Return a dictionary with various information about the system."""
    UNKNOWN = "unknown"
    info = {
        "windows_version": None,
        "mac_version": None,
        "linux_version": None,
        "linux_distro": None,
        "python_version": None,
    }

    if mozinfo.os == "mac":
        try:
            # Fetch the "release" from tuple containing macOS version information.
            # See https://docs.python.org/3/library/platform.html#macos-platform.
            info["mac_version"] = platform.mac_ver()[0]
        except (AttributeError, IndexError):
            info["mac_version"] = UNKNOWN
    elif mozinfo.os == "win":
        try:
            # Fetch "version" from tuple containing Windows version information.
            # See https://docs.python.org/3/library/platform.html#windows-platform.
            info["windows_version"] = platform.win32_ver()[1]
        except (AttributeError, IndexError):
            info["windows_version"] = UNKNOWN
    elif mozinfo.os == "linux":
        distro_info = distro.info()
        try:
            info["linux_version"] = distro_info["version"]
            info["linux_distro"] = distro_info["id"]
        except KeyError:
            info["linux_version"] = UNKNOWN
            info["linux_distro"] = UNKNOWN
    info["python_version"] = platform.python_version()
    return info


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

    # System information metrics.
    METRICS.usage.mac_version.set(metrics.mac_version)
    METRICS.usage.linux_version.set(metrics.linux_version)
    METRICS.usage.linux_distro.set(metrics.linux_distro)
    METRICS.usage.windows_version.set(metrics.windows_version)
    METRICS.usage.python_version.set(metrics.python_version)
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
