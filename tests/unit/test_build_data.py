import unittest
import requests
from mozregression import build_data, errors

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

if __name__ == '__main__':
    unittest.main()
