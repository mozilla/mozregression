# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import os
import tempfile


def safe_mkdtemp():
    '''
    Creates a temporary directory using mkdtemp, but makes sure that the
    returned directory is the full path on windows (see:
    https://bugzilla.mozilla.org/show_bug.cgi?id=1385928)
    '''
    tempdir = tempfile.mkdtemp()
    if os.name == 'nt':
        from ctypes import create_unicode_buffer, windll
        BUFFER_SIZE = 500
        buffer = create_unicode_buffer(BUFFER_SIZE)
        get_long_path_name = windll.kernel32.GetLongPathNameW
        get_long_path_name(unicode(tempdir), buffer, BUFFER_SIZE)
        return buffer.value
    else:
        return tempdir
