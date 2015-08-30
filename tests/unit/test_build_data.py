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

    def test_deleted(self):
        # make every point fetched
        self.build_data.half_window_range = 10
        self.build_data.ensure_limits()
        new_data = self.build_data.deleted(10)
        self.assertEqual(len(self.build_data), 20)
        self.assertEqual([new_data[i] for i in range(19)],
                         [i for i in range(20) if i != 10])

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
        self.build_data.mid_point()

        # now, size must be reduced by 3,
        # because the index 5 was not fetched yet
        self.assertEqual(len(self.build_data), 17)
        # the entire data list must be this:
        # - indexes 1, 9 and 10 are removed
        # - new indexes 3, 4, 11, 12 are not fetched yet.
        expected = [0, 2, 3, None, None, 6, 7, 8, 11,
                    12, 13, None, None, 16, 17, 18, 19]
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

    def test_index_of(self):
        self.assertEqual(self.build_data.index_of(lambda k: k[1] == 21), -1)
        self.assertEqual(self.build_data.index_of(lambda k: k[1] == 15), 15)


class TestNightlyBuildData(unittest.TestCase):
    def setUp(self):
        good_date = datetime.date(2014, 11, 10)
        bad_date = datetime.date(2014, 11, 20)
        fetch_config = fetch_configs.create_config('firefox', 'linux', 64)

        self.build_data = build_data.NightlyBuildData(fetch_config,
                                                      good_date,
                                                      bad_date)

    @patch('mozregression.build_data.NightlyBuildData._fetch')
    @patch('mozregression.build_data.MozBuildData.mid_point')
    def test_mid_point(self, mid_point, _fetch):
        # test with no data
        self.assertEqual(self.build_data[:0].mid_point(), 0)

        mid_point.return_value = 5
        result = self.build_data.mid_point()
        _fetch.assert_called_with(set([0, 5, 10]))
        self.assertTrue(mid_point.called)
        self.assertEqual(result, 5)


class TestInboundBuildData(unittest.TestCase):
    @patch('mozregression.build_data.JsonPushes.pushlog_within_changes')
    def create_inbound_build_data(self, good, bad, get_pushlogs):
        fetch_config = fetch_configs.create_config('firefox', 'linux', 64)
        # create fake pushlog returns
        pushlogs = [
            {'date': d, 'changesets': ['c' + str(d)]}
            for d in xrange(int(good[1:]), int(bad[1:]))
        ]
        get_pushlogs.return_value = pushlogs
        # returns 100 possible build folders

        return build_data.InboundBuildData(fetch_config, good, bad)

    def test_create_empty(self):
        data = self.create_inbound_build_data('c0', 'c0')
        self.assertEqual(len(data), 0)

    def test_create_only_one_rev(self):
        data = self.create_inbound_build_data('c0', 'c1')
        self.assertEqual(len(data), 1)

    def test_get_valid_build_got_exception(self):
        data = self.create_inbound_build_data('c0', 'c3')

        data.info_fetcher.find_build_info = \
            Mock(side_effect=errors.BuildInfoNotFound)

        data.mid_point()
        self.assertEqual(len(data), 0)


if __name__ == '__main__':
    unittest.main()
