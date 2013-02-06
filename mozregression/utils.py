# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import os
import re
import sys
import urllib2

from BeautifulSoup import BeautifulSoup

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

def download_url(url, dest=None, message="Downloading Nightly from:"):
    if os.path.exists(dest):
        print "Using local file: %s" % dest
        return

    if message:
        print "%s %s"%(message, url)

    CHUNK = 16 * 1024
    bytes_so_far = 0.0
    tmp_file = dest + ".part"
    r = urllib2.urlopen(url)
    total_size = int(r.info().getheader('Content-length').strip())
    if dest == None:
        dest = os.path.basename(url)
    
    f = open(tmp_file, 'wb')
    # write the file to the tmp_file
    for chunk in iter(lambda: r.read(CHUNK), ''):
        bytes_so_far += CHUNK
        f.write(chunk)
        percent = (bytes_so_far / total_size) * 100
        update_download_progress(percent)
    # move the temp file to the dest
    os.rename(tmp_file, dest)
    f.close()

    return dest

def urlLinks(url):
    r = urllib2.urlopen(url)
    content = r.read()
    if r.getcode() != 200:
        return []

    soup = BeautifulSoup(content)
    # do not return a generator but an array, so we can store it for later use
    return [link for link in soup.findAll('a')]
