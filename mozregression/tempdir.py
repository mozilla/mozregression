from __future__ import absolute_import

import os
import tempfile


def safe_mkdtemp():
    """
    Creates a temporary directory using mkdtemp, but makes sure that the
    returned directory is the full path on windows (see:
    https://bugzilla.mozilla.org/show_bug.cgi?id=1385928)
    """
    tempdir = tempfile.mkdtemp()
    if os.name == "nt":
        from ctypes import create_unicode_buffer, windll

        BUFFER_SIZE = 500
        buffer = create_unicode_buffer(BUFFER_SIZE)
        get_long_path_name = windll.kernel32.GetLongPathNameW
        get_long_path_name(str(tempdir), buffer, BUFFER_SIZE)
        return buffer.value
    else:
        return tempdir
