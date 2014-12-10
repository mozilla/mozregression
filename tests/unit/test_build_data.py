import unittest
import requests
import datetime
from mock import patch, Mock
from mozregression import build_data, errors, fetch_configs

class MyBuildData(build_data.BuildData):
    exc_to_raise = Exception('err')
    def __init__(self, ad):
        build_data.BuildData.__init__(self, ad)
        self.raises_for_indexes = {}

    def _create_fetch_task(self, executor, i):
        ad = self.get_associated_data(i)
        return executor.submit(self._return_data, ad)

    def _return_data(self, data):
        if data in self.raises_for_indexes:
            i = self.raises_for_indexes[data]
            if i > 0:
                self.raises_for_indexes[data] -= 1
                raise self.exc_to_raise
        return data

class TestBuildData(unittest.TestCase):
    def setUp(self):
        self.build_data = MyBuildData(range(20))

    def test_init(self):
        self.assertEqual(len(self.build_data), 20)
        # cache is empty
        self.assertEqual([self.build_data[i] for i in range(20)], [None] * 20)

    def test_slice(self):
        new_data = self.build_data[10:]
        self.assertEqual(len(self.build_data), 20)
        self.assertEqual(len(new_data), 10)

    def test_del(self):
        del self.build_data[10]
        self.assertEqual(len(self.build_data), 19)

    def test_mid_point(self):
        mid = self.build_data.mid_point()
        self.assertEqual(mid, 10)
        # check that mid point has been fetched
        self.assertEqual(self.build_data[mid], 10)
        # and also lower/upper bounds
        self.assertEqual(self.build_data[0], 0)
        self.assertEqual(self.build_data[-1], 19)
        # but for example point 5 was not
        self.assertEqual(self.build_data[5], None)

    def test_ensure_limits(self):
        self.build_data.half_window_range = 2
        self.build_data.ensure_limits()
        expected = [None] * 20
        for i in (0, 1, 18, 19):
            expected[i] = i
        # with a half_window_range of 2, we only have fetched the 2 first
        # lower and 2 last uppers
        self.assertEqual([self.build_data[i] for i in range(20)], expected)

    def test_with_invalid_data(self):
        # update associated data to make the fetched data return False
        # on some indexes
        invalid_indexes = (1, 5, 9, 10)
        for i in invalid_indexes:
            self.build_data._cache[i][1] = False

        # let's fetch some data
        mid = self.build_data.mid_point()

        # now, size must be reduced by 3, because the index 5 was not fetched yet
        self.assertEqual(len(self.build_data), 17)
        # the entire data list must be this:
        # - indexes 1, 9 and 10 are removed
        # - new indexes 3, 4, 11, 12 are not fetched yet.
        expected = [0, 2, 3, None, None, 6, 7, 8, 11, 12, 13, None, None, 16, 17, 18, 19]
        self.assertEqual([self.build_data[i] for i in range(17)], expected)

    def test_mid_point_when_no_more_data(self):
        # make every point invalid
        for i in range(20):
            self.build_data._cache[i][1] = False

        mid = self.build_data.mid_point()

        # everything was fetched there is no more data
        self.assertEqual(mid, 0)
        self.assertEqual(len(self.build_data), 0)

        # further calls won't break
        self.assertEqual(self.build_data.mid_point(), 0)

    def test_fetch_exception(self):
        # fetching index 10 will raise an exception
        self.build_data.raises_for_indexes[10] = 1
        # that ends up in a DownloadError exception
        self.assertRaises(errors.DownloadError, self.build_data.mid_point)

    def test_retry_on_http_errors(self):
        self.build_data.exc_to_raise = requests.HTTPError('err')

        # 2 http errors won't generate errors
        self.build_data.raises_for_indexes[10] = 2
        self.build_data.mid_point()

        # if 3 http errors are generated, it will be raised
        new_data = self.build_data[:10]
        new_data.raises_for_indexes[5] = 3
        self.assertRaises(errors.DownloadError, new_data.mid_point)

class TestBuildFolderInfoFetcher(unittest.TestCase):
    def setUp(self):
        self.info_fetcher = build_data.BuildFolderInfoFetcher(r'app_test.*.tar.bz2$',
                                                              r'app_test.*.txt$')

    @patch('mozregression.build_data.url_links')
    def test_find_build_info(self, url_links):
        url_links.return_value =  [
            'file1.txt.gz',
            'file2.txt',
            'app_test01linux-x86_64.txt',
            'app_test01linux-x86_64.tar.bz2',
        ]
        expected = {
            'build_txt_url': 'http://foo/app_test01linux-x86_64.txt',
            'build_url': 'http://foo/app_test01linux-x86_64.tar.bz2',
        }
        self.assertEqual(self.info_fetcher.find_build_info('http://foo'), expected)

    @patch('requests.get')
    def test_find_build_info_txt(self, get):
        response = Mock(text="20141101030205\nhttps://hg.mozilla.org/mozilla-central/rev/b695d9575654\n")
        get.return_value = response
        expected = {
            'repository': 'https://hg.mozilla.org/mozilla-central',
            'changeset': 'b695d9575654',
        }
        self.assertEqual(self.info_fetcher.find_build_info_txt('http://foo.txt'), expected)

class MyMozBuildData(build_data.MozBuildData):
    def get_build_urls(self, i):
        return ['http://foo/%d' % i]

class TestMozBuildData(unittest.TestCase):
    def setUp(self):
        info_fetcher = build_data.BuildFolderInfoFetcher(r'app_test.*.tar.bz2$',
                                                         r'app_test.*.txt$')
        self.build_data = MyMozBuildData(range(3), info_fetcher)

    @patch('mozregression.build_data.url_links')
    def test_fetch_builds(self, url_links):
        def _url_links(url):
            if url.endswith('0/'):
                # build folder 0 is empty
                return []
            if url.endswith('1/'):
                # build folder 1 lacks the build file
                return ['app_test01linux-x86_64.txt']
            # build folder 2 must be valid
            return ['app_test01linux-x86_64.txt', 'app_test01linux-x86_64.tar.bz2']
        url_links.side_effect = _url_links

        self.build_data.mid_point()
        self.assertEqual(len(self.build_data), 1)
        expected = {
            'build_url': 'http://foo/2/app_test01linux-x86_64.tar.bz2',
            'build_txt_url': 'http://foo/2/app_test01linux-x86_64.txt'
        }
        self.assertEqual(self.build_data[0], expected)

class TestNightlyUrlBuilder(unittest.TestCase):
    def setUp(self):
        fetch_config = fetch_configs.create_config('firefox', 'linux', 64)
        fetch_config.set_nightly_repo('foo')
        self.url_builder = build_data.NightlyUrlBuilder(fetch_config)

    @patch('mozregression.build_data.url_links')
    def test_get_url(self, url_links):
        url_links.return_value = [
            '2014-11-01-03-02-05-mozilla-central/',
            '2014-11-01-03-02-05-foo/',
            'foo',
            'bar/'
        ]
        urls = self.url_builder.get_urls(datetime.date(2014, 11, 01))
        self.assertEqual(urls[0], 'http://ftp.mozilla.org/pub/mozilla.org/firefox/nightly/2014/11/2014-11-01-03-02-05-foo/')
        urls = self.url_builder.get_urls(datetime.date(2014, 11, 02))
        self.assertEqual(urls, [])

if __name__ == '__main__':
    unittest.main()
