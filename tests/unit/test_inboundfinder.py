import unittest
from mock import patch, Mock
from mozregression import inboundfinder, errors

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
