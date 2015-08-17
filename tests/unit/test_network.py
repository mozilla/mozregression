import unittest
import requests

from mock import patch, Mock
from mozregression import network, limitedfilecache


class TestUrlLinks(unittest.TestCase):
    @patch('requests.get')
    def test_url_no_links(self, get):
        get.return_value = Mock(text='')
        self.assertEquals(network.url_links(''), [])

    @patch('requests.get')
    def test_url_with_links(self, get):
        get.return_value = Mock(text="""
        <body>
        <a href="thing/">thing</a>
        <a href="thing2/">thing2</a>
        </body>
        """)
        self.assertEquals(network.url_links(''),
                          ['thing/', 'thing2/'])

    @patch('requests.get')
    def test_url_with_links_regex(self, get):
        get.return_value = Mock(text="""
        <body>
        <a href="thing/">thing</a>
        <a href="thing2/">thing2</a>
        </body>
        """)
        self.assertEquals(
            network.url_links('', regex="thing2.*"),
            ['thing2/'])


class TestHTTPCache(unittest.TestCase):
    def setUp(self):
        self.addCleanup(network.set_http_cache_session, None)

    def make_cache(self):
        return limitedfilecache.get_cache(
            '/fakedir', limitedfilecache.ONE_GIGABYTE, logger=None)

    def test_basic(self):
        self.assertEquals(network.get_http_session(), requests)

    def test_none_returns_requests(self):
        network.set_http_cache_session(self.make_cache())
        network.set_http_cache_session(None)
        self.assertEquals(network.get_http_session(), requests)

    def test_get_http_session(self):
        network.set_http_cache_session(self.make_cache())
        a_session = network.get_http_session()

        # verify session exists
        self.assertTrue(isinstance(a_session, requests.Session))

        # turns out CacheControl is just a function not a class
        # so it makes verifying that we're actually using it
        # a little messy
        for k, v in a_session.adapters.items():
            self.assertTrue(isinstance(v.cache,
                            limitedfilecache.LimitedFileCache))

    def test_set_http_session_with_get_defaults(self):
        original_get = Mock()
        session = Mock(get=original_get)
        network.set_http_cache_session(session, get_defaults={"timeout": 10.0})
        # default is applied
        network.get_http_session().get('url')
        original_get.assert_called_with('url', timeout=10.0)
        # this is just a default, it can be overriden
        network.get_http_session().get('url', timeout=5.0)
        original_get.assert_called_with('url', timeout=5.0)
        # you can still pass a None session
        with patch('requests.Session') as Session:
            Session.return_value = session
            network.set_http_cache_session(None, get_defaults={'timeout': 1.0})
            # a new session has been returned
            self.assertEquals(session, network.get_http_session())
            # with defaults patch too
            network.get_http_session().get('url')
            original_get.assert_called_with('url', timeout=1.0)

if __name__ == '__main__':
    unittest.main()
