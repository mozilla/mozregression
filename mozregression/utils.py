# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Utility functions and classes for mozregression.
"""

import datetime
import os
import re
import sys
from BeautifulSoup import BeautifulSoup
import mozinfo
import requests
import mozfile

from mozregression import errors


class ClassRegistry(object):
    """
    A registry to store classes identified by a unique name.

    :param attr_name: On each registered class, the unique name will be saved
                      under this class attribute name.
    """
    def __init__(self, attr_name='name'):
        self._classes = {}
        self.attr_name = attr_name

    def register(self, name, attr_value=None):
        """
        Register a class with a given name.

        :param name: name to identify the class
        :param attr_value: If given, it will be used to define the value of
                           the class attribute. If not given, *name* is used.
        """
        assert name not in self._classes

        def wrapper(klass):
            self._classes[name] = klass
            setattr(klass, self.attr_name, attr_value or name)
            return klass
        return wrapper

    def get(self, name):
        """
        Returns a registered class.
        """
        return self._classes[name]

    def names(self):
        """
        Returns a list of registered class names.
        """
        return sorted(self._classes)

CACHE_SESSION = None


def set_http_cache_session(cache_session, get_defaults=None):
    """
    Define a cache http session.

    :param cache_session: a customized request session (possibly using
        CacheControl) or None to use a simple request session.
    :param: get_defaults: if defined, it must be a dict that will provide
        default values for calls to cache_session.get.
    """
    global CACHE_SESSION
    if get_defaults:
        if cache_session is None:
            cache_session = requests.Session()
        # monkey patch to set default values to a session.get calls
        # I don't see other ways to do this globally for timeout for example
        _get = cache_session.get

        def _default_get(*args, **kwargs):
            for k, v in get_defaults.iteritems():
                kwargs.setdefault(k, v)
            return _get(*args, **kwargs)
        cache_session.get = _default_get
    CACHE_SESSION = cache_session


def get_http_session():
    """
    Returns the defined http session.
    """
    return CACHE_SESSION or requests


def parse_date(date_string):
    """
    Returns a date from a string.
    """
    regex = re.compile(r'(\d{4})\-(\d{1,2})\-(\d{1,2})')
    matched = regex.match(date_string)
    if not matched:
        raise errors.DateFormatError(date_string)
    return datetime.date(int(matched.group(1)),
                         int(matched.group(2)),
                         int(matched.group(3)))


def parse_bits(option_bits):
    """
    Returns the correctly typed bits.
    """
    if option_bits == "32":
        return 32
    else:
        # if 64 bits is passed on a 32 bit system, it won't be honored
        return mozinfo.bits


def update_download_progress(percent):
    """
    Print realtime status of downloaded file.
    """
    sys.stdout.write("===== Downloaded %d%% =====\r" % percent)
    sys.stdout.flush()
    if percent >= 100:
        sys.stdout.write("\n")


def download_url(url, dest):
    """
    Download a file given an url.
    """
    chunk_size = 16 * 1024
    bytes_so_far = 0.0
    tmp_file = dest + ".part"
    response = get_http_session().get(url, stream=True)
    total_size = int(response.headers['Content-length'].strip())

    try:
        with open(tmp_file, 'wb') as ftmp:
            # write the file to the tmp_file
            for chunk in response.iter_content(chunk_size=chunk_size):
                # Filter out Keep-Alive chunks.
                if not chunk:
                    continue
                bytes_so_far += chunk_size
                ftmp.write(chunk)
                percent = (bytes_so_far / total_size) * 100
                update_download_progress(percent)
    except:
        if os.path.isfile(tmp_file):
            mozfile.remove(tmp_file)
        raise

    # move the temp file to the dest
    os.rename(tmp_file, dest)

    return dest


def url_links(url, regex=None, auth=None):
    """
    Returns a list of links that can be found on a given web page.
    """
    response = get_http_session().get(url, auth=auth)
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


def get_build_regex(name, os, bits, with_ext=True):
    """
    Returns a string regexp that can match a build filename.

    :param name: must be the beginning of the filename to match
    :param os: the os, as returned by mozinfo.os
    :param bits: the bits information of the build. Either 32 or 64.
    :param with_ext: if True, the build extension will be appended (either
                     .zip, .tar.bz2 or .dmg depending on the os).
    """
    if os == "win":
        if bits == 64:
            suffix, ext = r".*win64(-x86_64)?", r"\.zip"
        else:
            suffix, ext = r".*win32", r"\.zip"
    elif os == "linux":
        if bits == 64:
            suffix, ext = r".*linux-x86_64", r"\.tar.bz2"
        else:
            suffix, ext = r".*linux-i686", r"\.tar.bz2"
    elif os == "mac":
        suffix, ext = r".*mac.*", r"\.dmg"

    regex = '%s%s' % (name, suffix)
    if with_ext:
        return '%s%s' % (regex, ext)
    else:
        return regex


def releases():
    """
    Provide the list of releases with their associated dates.

    The date is a string formated as "yyyy-mm-dd", and the release an integer.
    """
    return {
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
        35: "2014-10-13",
        36: "2014-11-28",
        37: "2015-01-12"
    }


def date_of_release(release):
    """
    Provide the date of a release.
    """
    try:
        return releases()[release]
    except KeyError:
        raise errors.UnavailableRelease(release)


def formatted_valid_release_dates():
    """
    Returns a formatted string (ready to be printed) representing
    the valid release dates.
    """
    message = "Valid releases: \n"
    for key, value in releases().iteritems():
        message += '% 3s: %s\n' % (key, value)

    return message
