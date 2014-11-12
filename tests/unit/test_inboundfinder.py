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

class FakeBuildsFinder(inboundfinder.BuildsFinder):
    default_inbound_branch = 'mozregression-test'
    def _get_build_base_url(self, inbound_branch):
        return "/"

    def _create_pushlog_finder(self, start_rev, end_rev):
        class FakePushlogFinder:
            def get_pushlogs(self):
                return [
                    {'date': i, 'changesets': [i]} for i in range(start_rev, end_rev)
                ]
        return FakePushlogFinder()

    def _extract_paths(self):
        return [(str(i), i) for i in range(20)]

class TestBuildsFinder(unittest.TestCase):
    def test_get_build_infos(self):
        build_finder = FakeBuildsFinder()
        infos = build_finder.get_build_infos(0, 20)
        self.assertEquals(len(infos), 20)

    def test_get_build_infos_with_range(self):
        build_finder = FakeBuildsFinder()
        infos = build_finder.get_build_infos(5, 15, range=2)
        self.assertEquals(len(infos), 12)

class ConcreteBuildsFinder(unittest.TestCase):
    builder_class = None
    def assert_build_url(self, os, bits, url, inbound_branch=None):
        build_finder = self.builder_class(os=os, bits=bits, inbound_branch=inbound_branch)
        self.assertEquals(build_finder.build_base_url, url)

class TestFennecBuildsFinder(ConcreteBuildsFinder):
    builder_class = inboundfinder.FennecBuildsFinder
    def test_build_finder(self):
        configs = [('linux', 64, 'android'),]
        for inbound_branch in (None, 'test-branch'):
            for (os, bits, suffix) in configs:
                expected_branch = inbound_branch if inbound_branch else 'mozilla-inbound'

                good_url = "http://inbound-archive.pub.build.mozilla.org/pub/mozilla.org" \
                           "/mobile/tinderbox-builds/%s-%s/" % (expected_branch, suffix)
                self.assert_build_url(os, bits, good_url, inbound_branch)

class TestFirefoxBuildsFinder(ConcreteBuildsFinder):
    builder_class = inboundfinder.FirefoxBuildsFinder
    def test_build_finder(self):
        configs = [('linux', 64, 'linux64'), ('linux', 32, 'linux'),
                   ('win', 32, 'win32'), ('mac', 64, 'macosx64')]
        for inbound_branch in (None, 'test-branch'):
            for (os, bits, suffix) in configs:
                expected_branch = inbound_branch if inbound_branch else 'mozilla-inbound'
                good_url = 'http://inbound-archive.pub.build.mozilla.org/pub' \
                           '/mozilla.org/firefox/tinderbox-builds/%s-%s/' % \
                           (expected_branch, suffix)
                self.assert_build_url(os, bits, good_url, inbound_branch)

    def test_build_finder_win64(self):
        with self.assertRaises(errors.Win64NoAvailableBuildError):
            self.assert_build_url('win', 64, "")

class TestB2GBuildsFinder(ConcreteBuildsFinder):
    builder_class = inboundfinder.B2GBuildsFinder
    def test_build_finder(self):
        configs = [('linux', 64, 'linux64'), ('linux', 32, 'linux32'),
                   ('win', 32, 'win32'), ('mac', 64, 'macosx64')]
        for inbound_branch in (None, 'test-branch'):
            for (os, bits, suffix) in configs:
                expected_branch = inbound_branch if inbound_branch else 'b2g-inbound'
                good_url = 'http://ftp.mozilla.org/pub/mozilla.org/b2g'\
                           '/tinderbox-builds/%s-%s_gecko/' % \
                           (expected_branch, suffix)
                self.assert_build_url(os, bits, good_url, inbound_branch)

    def test_build_finder_win64(self):
        with self.assertRaises(errors.Win64NoAvailableBuildError):
            self.assert_build_url('win', 64, "")
