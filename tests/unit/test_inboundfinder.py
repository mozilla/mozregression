import unittest
from mock import patch, Mock
from mozregression import inboundfinder

class TestPushLogsFinder(unittest.TestCase):
    def test_pushlog_url(self):
        finder = inboundfinder.PushLogsFinder("azerty", "uiop")
        good_url = 'https://hg.mozilla.org/integration/mozilla-inbound/json-pushes' \
                   '?fromchange=azerty&tochange=uiop'
        self.assertEquals(finder.pushlog_url(), good_url)

    def test_custom_pushlog_url(self):
        finder = inboundfinder.PushLogsFinder("1", "2", path="3", branch="4")
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
    def _get_build_base_url(self):
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

    def _get_valid_builds(self, build_url, timestamp, raw_revisions):
        return [(build_url, timestamp, raw_revisions)]

    def _sort_builds(self, builds):
        return sorted(builds, key=lambda b: b[1])

class TestBuildsFinder(unittest.TestCase):
    def test_get_build_infos(self):
        build_finder = FakeBuildsFinder()
        infos = build_finder.get_build_infos(0, 20)
        self.assertEquals(infos, [('/%d/' % i, i, range(20)) for i in range(0, 20)])

    def test_get_build_infos_with_range(self):
        build_finder = FakeBuildsFinder()
        infos = build_finder.get_build_infos(5, 15, range=2)
        self.assertEquals(infos, [('/%d/' % i, i, range(5, 15)) for i in range(4, 16)])

class ConcreteBuildsFinder(unittest.TestCase):
    builder_class = None
    def assert_build_url(self, os, bits, url):
        build_finder = self.builder_class(os=os, bits=bits)
        self.assertEquals(build_finder.build_base_url, url)

class TestFennecBuildsFinder(ConcreteBuildsFinder):
    builder_class = inboundfinder.FennecBuildsFinder
    def test_build_finder(self):
        good_url = "http://inbound-archive.pub.build.mozilla.org/pub/mozilla.org" \
                   "/mobile/tinderbox-builds/mozilla-inbound-android/"
        self.assert_build_url('linux', 64, good_url)

class TestFirefoxBuildsFinder(ConcreteBuildsFinder):
    builder_class = inboundfinder.FirefoxBuildsFinder
    def test_build_finder_linux64(self):
        good_url = 'http://inbound-archive.pub.build.mozilla.org/pub' \
                   '/mozilla.org/firefox/tinderbox-builds/mozilla-inbound-linux64/'
        self.assert_build_url('linux', 64, good_url)

    def test_build_finder_linux32(self):
        good_url = 'http://inbound-archive.pub.build.mozilla.org/pub' \
                   '/mozilla.org/firefox/tinderbox-builds/mozilla-inbound-linux/'
        self.assert_build_url('linux', 32, good_url)

    def test_build_finder_win32(self):
        good_url = 'http://inbound-archive.pub.build.mozilla.org/pub' \
                   '/mozilla.org/firefox/tinderbox-builds/mozilla-inbound-win32/'
        self.assert_build_url('win', 32, good_url)

    def test_build_finder_win64(self):
        with self.assertRaises(SystemExit):
            self.assert_build_url('win', 64, "")

    def test_build_finder_mac64(self):
        good_url = 'http://inbound-archive.pub.build.mozilla.org/pub' \
                   '/mozilla.org/firefox/tinderbox-builds/mozilla-inbound-macosx64/'
        self.assert_build_url('mac', 64, good_url)

class TestB2GBuildsFinder(ConcreteBuildsFinder):
    builder_class = inboundfinder.B2GBuildsFinder
    def test_build_finder_linux64(self):
        good_url = 'http://ftp.mozilla.org/pub/mozilla.org/b2g'\
                   '/tinderbox-builds/b2g-inbound-linux64_gecko/'
        self.assert_build_url('linux', 64, good_url)

    def test_build_finder_linux32(self):
        good_url = 'http://ftp.mozilla.org/pub/mozilla.org/b2g'\
                   '/tinderbox-builds/b2g-inbound-linux32_gecko/'
        self.assert_build_url('linux', 32, good_url)

    def test_build_finder_win32(self):
        good_url = 'http://ftp.mozilla.org/pub/mozilla.org/b2g'\
                   '/tinderbox-builds/b2g-inbound-win32_gecko/'
        self.assert_build_url('win', 32, good_url)

    def test_build_finder_win64(self):
        with self.assertRaises(SystemExit):
            self.assert_build_url('win', 64, "")

    def test_build_finder_mac64(self):
        good_url = 'http://ftp.mozilla.org/pub/mozilla.org/b2g'\
                   '/tinderbox-builds/b2g-inbound-macosx64_gecko/'
        self.assert_build_url('mac', 64, good_url)
