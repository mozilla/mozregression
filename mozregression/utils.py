# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import re
import httplib2
import datetime

def strsplit(string, sep):
    # XXX https://github.com/mozilla/mozregression/issues/50
    strlist = string.split(sep)
    if strlist == ['']:
      return []
    return strlist

def download_url(url, dest=None):
    h = httplib2.Http()
    resp, content = h.request(url, "GET")
    if dest == None:
        dest = os.path.basename(url)

    local = open(dest, 'wb')
    local.write(content)
    local.close()
    return dest

def get_date(dateString):
    p = re.compile('(\d{4})\-(\d{1,2})\-(\d{1,2})')
    m = p.match(dateString)
    if not m:
        print "Incorrect date format"
        return
    return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
