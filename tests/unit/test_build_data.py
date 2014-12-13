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

    def test_mid_point_when_not_enough_data(self):
        # make two points valids only
        invalid_indexes = range(18)
        for i in invalid_indexes:
            self.build_data._cache[i][1] = False

        mid = self.build_data.mid_point()
        self.assertEqual(mid, 0)

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

class TestNightlyBuildData(unittest.TestCase):
    def setUp(self):
        good_date = datetime.date(2014, 11, 10)
        bad_date = datetime.date(2014, 11, 20)
        fetch_config = fetch_configs.create_config('firefox', 'linux', 64)

        self.build_data = build_data.NightlyBuildData(good_date, bad_date, fetch_config)

    def test_date_for_index(self):
        date = self.build_data.get_date_for_index(0)
        self.assertEqual(date, datetime.date(2014, 11, 10))
        date = self.build_data.get_date_for_index(-1)
        self.assertEqual(date, datetime.date(2014, 11, 20))
        date = self.build_data.get_date_for_index(5)
        self.assertEqual(date, datetime.date(2014, 11, 15))

    @patch('mozregression.build_data.BuildFolderInfoFetcher.find_build_info_txt')
    @patch('mozregression.build_data.BuildFolderInfoFetcher.find_build_info')
    @patch('mozregression.build_data.NightlyUrlBuilder.get_urls')
    def test_get_valid_build_for_date(self, get_urls, find_build_info, find_build_info_txt):
        get_urls.return_value = [
            'http://ftp.mozilla.org/pub/mozilla.org/bar/nightly/2014/11/2014-11-15-08-02-05-mozilla-central/',
            'http://ftp.mozilla.org/pub/mozilla.org/bar/nightly/2014/11/2014-11-15-04-02-05-mozilla-central/',
            'http://ftp.mozilla.org/pub/mozilla.org/bar/nightly/2014/11/2014-11-15-03-02-05-mozilla-central/',
            'http://ftp.mozilla.org/pub/mozilla.org/bar/nightly/2014/11/2014-11-15-02-02-05-mozilla-central/',
            'http://ftp.mozilla.org/pub/mozilla.org/bar/nightly/2014/11/2014-11-15-01-02-05-mozilla-central/',
        ]

        def my_find_build_info(url):
            # say only the last build url is invalid
            if url in get_urls.return_value[:-1]:
                return {}
            return {
                'build_txt_url': url,
                'build_url': url,
            }
        find_build_info.side_effect = my_find_build_info
        result = self.build_data._get_valid_build_for_date(datetime.date(2014, 11, 15), True)
        # we must have found the last build url valid
        self.assertEqual(result, {
            'build_txt_url': get_urls.return_value[-1],
            'build_url': get_urls.return_value[-1],
        })

    @patch('mozregression.build_data.NightlyUrlBuilder.get_urls')
    def test_get_valid_build_for_date_no_data(self, get_urls):
        get_urls.return_value = []
        result = self.build_data._get_valid_build_for_date(datetime.date(2014, 11, 15))
        self.assertEqual(False, result)

    @patch('mozregression.build_data.NightlyBuildData._get_valid_build_for_date')
    def test_get_valid_build(self, _get_valid_build_for_date):
        self.build_data._get_valid_build(5)
        _get_valid_build_for_date.assert_called_with(datetime.date(2014, 11, 15))

    @patch('mozregression.build_data.NightlyBuildData._get_valid_build_for_date')
    def test_build_infos_for_date(self, _get_valid_build_for_date):
        _get_valid_build_for_date.return_value = False
        date = datetime.date(2015, 11, 15)
        result = self.build_data.get_build_infos_for_date(date)
        _get_valid_build_for_date.assert_called_with(date, True)
        self.assertEqual(result, {})

    @patch('mozregression.build_data.NightlyBuildData._fetch')
    @patch('mozregression.build_data.MozBuildData.mid_point')
    def test_mid_point(self, mid_point, _fetch):
        # test with no data
        self.assertEqual(self.build_data[:0].mid_point(), 0)

        mid_point.return_value = 5
        result = self.build_data.mid_point()
        _fetch.assert_called_with(set([0, 5, 10]))
        mid_point.assert_called()
        self.assertEqual(result, 5)

if __name__ == '__main__':
    unittest.main()
