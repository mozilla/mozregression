# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
import requests
import warnings

from cachecontrol import CacheControl
from cachecontrol.caches import FileCache

ONE_GIGABYTE = 1000000000


def get_cache(directory, max_bytes, logger):
    forever = True if directory else False
    if forever:
        fc = LimitedFileCache(directory, forever=forever,
                              max_bytes=max_bytes, logger=logger)
        return CacheControl(requests.session(), cache=fc)
    else:
        # not forever so just cache within this run
        return CacheControl(requests.session())


class LimitedFileCache(FileCache):
    def __init__(self, directory, forever=False, filemode=0o0600,
                 dirmode=0o0700, max_bytes=ONE_GIGABYTE, logger=warnings):
        FileCache.__init__(self, directory, forever, filemode, dirmode)
        self.max_bytes = max_bytes
        self.curr_bytes = 0
        self.logger = logger

    def set(self, key, value):
        new_bytes = sys.getsizeof(value)
        total = (self.curr_bytes + new_bytes)
        if total > self.max_bytes:
            message = "Tried adding %d bytes but %d bytes are currently saved" \
                      " in the cache and the max_bytes is set to %d.\n" % \
                      (new_bytes, self.curr_bytes, self.max_bytes)
            self.logger.warn(message)
            return

        FileCache.set(self, key, value)

        self.curr_bytes += new_bytes

    def delete(self, key):
        value = self.get(key)
        FileCache.delete(self, key)
        removed_bytes = sys.getsizeof(value)
        if not self.forever:
            self.curr_bytes -= removed_bytes
