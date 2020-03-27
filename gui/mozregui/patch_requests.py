import os
import sys

# only True when running from frozen (bundled) app
IS_FROZEN = getattr(sys, "frozen", False)


def cacert_path():
    """return the path to cacert.pem (or None if not required)"""
    if IS_FROZEN:
        return os.path.join(os.path.dirname(sys.executable), "cacert.pem")


def patch():
    # patch requests.request so taskcluster can use the right cacert.pem file.
    if IS_FROZEN:
        import requests

        pem = cacert_path()
        old_request = requests.request

        def _patched_request(*args, **kwargs):
            kwargs["verify"] = pem
            return old_request(*args, **kwargs)

        requests.request = _patched_request
