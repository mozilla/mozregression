import unittest
from mock import patch, Mock
import requests
from mozregression import inboundfinder, errors
from mozregression import utils

class TestPushLogsFinder(unittest.TestCase):
    def test_pushlog_url(self):
        finder = inboundfinder.PushLogsFinder("azerty", "uiop")
        good_url = 'https://hg.mozilla.org/integration/mozilla-inbound/json-pushes' \
                   '?fromchange=azerty&tochange=uiop'
        self.assertEquals(finder.pushlog_url(), good_url)

    def test_custom_pushlog_url(self):
        finder = inboundfinder.PushLogsFinder("1", "2", path="3", inbound_branch="4")
        good_url = 'https://hg.mozilla.org/3/4/json-pushes' \
                   '?fromchange=1&tochange=2'
        self.assertEquals(finder.pushlog_url(), good_url)

    @patch('requests.get')
    def test_get_pushlogs(self, get):
        get.return_value = Mock(json=lambda:{
            1456: {'date': 1},
            1234: {'date': 12},
            5789: {'date': 5},
        })
        finder = inboundfinder.PushLogsFinder("azerty", "uiop")
        self.assertEquals(finder.get_pushlogs(), [
            {'date': 1},
            {'date': 5},
            {'date': 12},
        ])

class TestInboundFinder(unittest.TestCase):
    def setUp(self):
        self.addCleanup(utils.set_http_cache_session, None)

    def test_exit_on_omitted_start_and_end_rev(self):
        with self.assertRaises(SystemExit) as se:
            actual = inboundfinder.get_build_finder([])

        self.assertEqual(se.exception.code,
            'start revision and end revision must be specified')

    def test_get_app(self):
        argv = ['inboundfinder', '--start-rev=1', '--end-rev=2',]
        actual = inboundfinder.get_build_finder(argv)
        self.assertTrue(isinstance(actual, inboundfinder.BuildsFinder))

        # default is to use a cache session
        a_session = utils.get_http_session()
        self.assertTrue(isinstance(a_session, requests.Session))
