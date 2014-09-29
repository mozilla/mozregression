# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import os
import re
import sys

from BeautifulSoup import BeautifulSoup
import requests


def get_date(date_string):
    regex = re.compile(r'(\d{4})\-(\d{1,2})\-(\d{1,2})')
    matched = regex.match(date_string)
    if not matched:
        print "Incorrect date format"
        return
    return datetime.date(int(matched.group(1)),
                         int(matched.group(2)),
                         int(matched.group(3)))


def update_download_progress(percent):
    sys.stdout.write("===== Downloaded %d%% =====\r" % percent)
    sys.stdout.flush()
    if percent >= 100:
        sys.stdout.write("\n")


def download_url(url, dest=None, message="Downloading build from:"):
    if os.path.exists(dest):
        print "Using local file: %s" % dest
        return

    if message:
        print "%s %s" % (message, url)

    chunk_size = 16 * 1024
    bytes_so_far = 0.0
    tmp_file = dest + ".part"
    request = requests.get(url, stream=True)
    total_size = int(request.headers['Content-length'].strip())
    if dest is None:
        dest = os.path.basename(url)

    with open(tmp_file, 'wb') as ftmp:
        # write the file to the tmp_file
        for chunk in request.iter_content(chunk_size=chunk_size):
            # Filter out Keep-Alive chunks.
            if not chunk:
                continue
            bytes_so_far += chunk_size
            ftmp.write(chunk)
            percent = (bytes_so_far / total_size) * 100
            update_download_progress(percent)
    # move the temp file to the dest
    os.rename(tmp_file, dest)

    return dest


def url_links(url, regex=None, auth=None):
    response = requests.get(url, auth=auth)
    response.raise_for_status()

    soup = BeautifulSoup(response.text)

    if regex:
        if isinstance(regex, basestring):
            regex = re.compile(regex)
        match = regex.match
    else:
        match = lambda t: True

    # do not return a generator but an array, so we can store it for later use
    return [link.get('href')
            for link in soup.findAll('a')
            if match(link.get('href'))]

def date_of_release(release):
    """Provide the date of a release.
    The date is a string formated as "yyyy-mm-dd",
    and the release an integer.
    """
    releases = {
        5: "2011-04-12",
        6: "2011-05-24",
        7: "2011-07-05",
        8: "2011-08-16",
        9: "2011-09-27",
        10: "2011-11-08",
        11: "2011-12-20",
        12: "2012-01-31",
        13: "2012-03-13",
        14: "2012-04-24",
        15: "2012-06-05",
        16: "2012-07-16",
        17: "2012-08-27",
        18: "2012-10-08",
        19: "2012-11-19",
        20: "2013-01-07",
        21: "2013-02-19",
        22: "2013-04-01",
        23: "2013-05-13",
        24: "2013-06-24",
        25: "2013-08-05",
        26: "2013-09-16",
        27: "2013-10-28",
        28: "2013-12-09",
        29: "2014-02-03",
        30: "2014-03-17",
        31: "2014-04-28",
        32: "2014-06-09",
        33: "2014-07-21",
        34: "2014-09-02",
    }
    if release in releases:
        return releases[release]
    return None
