# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
network functions utilities for mozregression.
"""

import re
import redo
import requests

from BeautifulSoup import BeautifulSoup


def retry_get(url, **karwgs):
    """
    More robust `requests.get` equivalent function.

    This is equivalent to the requests.get function, except that
    it will retry the requests call three times in case of HTTPError or
    ConnectionError.
    """
    return redo.retry(get_http_session().get, attempts=3, sleeptime=1,
                      retry_exceptions=(requests.exceptions.HTTPError,
                                        requests.exceptions.ConnectionError),
                      args=(url,), kwargs=karwgs)


SESSION = None


def set_http_session(session=None, get_defaults=None):
    """
    Define a cache http session.

    :param cache_session: a customized request session or None to use a
                          simple request session.
    :param: get_defaults: if defined, it must be a dict that will provide
        default values for calls to cache_session.get.
    """
    global SESSION
    if get_defaults:
        if session is None:
            session = requests.Session()
        # monkey patch to set default values to a session.get calls
        # I don't see other ways to do this globally for timeout for example
        _get = session.get

        def _default_get(*args, **kwargs):
            for k, v in get_defaults.iteritems():
                kwargs.setdefault(k, v)
            return _get(*args, **kwargs)
        session.get = _default_get
    SESSION = session


def get_http_session():
    """
    Returns the defined http session.
    """
    return SESSION or requests


def url_links(url, regex=None, auth=None):
    """
    Returns a list of links that can be found on a given web page.

    Note that it href of links found are starting with '/' (absolute url from
    the server point of view) then only the last part of the link will be
    returned. E.G:

    '/pub/firefox/nightly/2015/03/2015-03-02-03-02-04-mozilla-central/'
    will return '2015-03-02-03-02-04-mozilla-central/'.
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
    result = []
    for link in soup.findAll('a'):
        href = link.get('href')
        # return "relative" part of the url only
        if href.startswith('/'):
            if href.endswith('/'):
                href = href.strip('/').rsplit('/', 1)[-1] + '/'
            else:
                href = href.rsplit('/', 1)[-1]
        if match(href):
            result.append(href)
    return result
