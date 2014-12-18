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
        def my_get(url):
            result = None
            if url.endswith('?changeset=azerty'):
                # return one value for this particular changeset
                result = Mock(json=lambda: {1456: {'date': 1}})
            elif url.endswith('?fromchange=azerty&tochange=uiop'):
                # here comes the changeset between ou fake ones,
                # qzerty (not included) and uiop.
                result = Mock(json=lambda: {
                    1234: {'date': 12},
                    5789: {'date': 5},
                })
            return result
        get.side_effect = my_get
        finder = inboundfinder.PushLogsFinder("azerty", "uiop")
        # check that changesets are merged and ordered
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
