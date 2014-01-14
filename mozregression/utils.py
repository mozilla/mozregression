# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import os
import re
import sys

from BeautifulSoup import BeautifulSoup
import requests

def strsplit(string, sep):
    # XXX https://github.com/mozilla/mozregression/issues/50
    strlist = string.split(sep)
    if strlist == ['']:
      return []
    return strlist

def get_date(dateString):
    p = re.compile('(\d{4})\-(\d{1,2})\-(\d{1,2})')
    m = p.match(dateString)
    if not m:
        print "Incorrect date format"
        return
    return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

def update_download_progress(percent):
    sys.stdout.write("===== Downloaded %d%% =====\r"%percent)
    sys.stdout.flush()
    if percent >= 100:
        sys.stdout.write("\n")

def download_url(url, dest=None, message="Downloading build from:"):
    if os.path.exists(dest):
        print "Using local file: %s" % dest
        return

    if message:
        print "%s %s"%(message, url)

    CHUNK = 16 * 1024
    bytes_so_far = 0.0
    tmp_file = dest + ".part"
    r = requests.get(url, stream=True)
    total_size = int(r.headers['Content-length'].strip())
    if dest == None:
        dest = os.path.basename(url)

    f = open(tmp_file, 'wb')
    # write the file to the tmp_file
    for chunk in r.iter_content(chunk_size=CHUNK):
        # Filter out Keep-Alive chunks.
        if not chunk:
            continue
        bytes_so_far += CHUNK
        f.write(chunk)
        percent = (bytes_so_far / total_size) * 100
        update_download_progress(percent)
    f.close()
    # move the temp file to the dest
    os.rename(tmp_file, dest)

    return dest

def urlLinks(url):
    r = requests.get(url)
    content = r.text
    if r.status_code != 200:
        return []

    soup = BeautifulSoup(content)
    # do not return a generator but an array, so we can store it for later use
    return [link for link in soup.findAll('a')]
