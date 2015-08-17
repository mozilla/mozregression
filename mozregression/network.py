# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
network functions and classes for mozregression.
"""

import re
import redo
import requests

from BeautifulSoup import BeautifulSoup


def retry_get(url, **karwgs):
    return redo.retry(get_http_session().get, attempts=3, sleeptime=1,
                      retry_exceptions=(requests.exceptions.HTTPError,
                                        requests.exceptions.ConnectionError),
                      args=(url,), kwargs=karwgs)

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


def url_links(url, regex=None, auth=None):
    """
    Returns a list of links that can be found on a given web page.
    """
    response = retry_get(url, auth=auth)
    response.raise_for_status()

    soup = BeautifulSoup(response.text)

    if regex:
        if isinstance(regex, basestring):
            regex = re.compile(regex)
        match = regex.match
    else:
        def match(_):
            return True

    # do not return a generator but an array, so we can store it for later use
    return [link.get('href')
            for link in soup.findAll('a')
            if match(link.get('href'))]
