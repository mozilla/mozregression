import unittest
from mock import patch, Mock
from mozregression import errors
from mozregression.regression import Bisector
from mozregression.fetch_configs import FirefoxConfig
from mozregression import launchers
from test_build_data import MyBuildData

class MyBisector(Bisector):
    def __init__(self, fetch_config, options,
                 last_good_revision=None, first_bad_revision=None):
        self.last_good_revision = last_good_revision
        self.first_bad_revision = first_bad_revision
        self.fetch_config = fetch_config
        self.options = options
        self.http_cache_dir = options.http_cache_dir
        self._logger = Mock(info=lambda a: None)

class TestBisector(unittest.TestCase):
    def setUp(self):
        self.fetch_config = Mock(inbound_branch='my-inbound-branch')
        self.persist = None
        self.options = Mock(persist=self.persist)
        self.bisector = MyBisector(self.fetch_config, self.options,
            '17de0f463944', '035a951fc24a')
        self.build_data = MyBuildData(range(20))

    @staticmethod
    def fake_create_launcher(name, url, persist=None, persist_prefix=''):
      return (name, url, persist, persist_prefix)

    @patch('mozregression.regression.create_launcher')
    @patch('mozregression.build_data.BuildData.__getitem__')
    @patch('mozregression.inboundfinder.BuildsFinder.get_build_infos')
    def test_prepare_bisect(self, get_build_infos, getitem, create_launcher):
        get_build_infos.return_value = self.build_data

        expected_base = 'http://some_url'
        expected_full_url = '%s-%s-' % (expected_base,
                                        self.fetch_config.inbound_branch)
        mid_mock = Mock(__getitem__= lambda a, b: expected_base)
        getitem.return_value = mid_mock

        create_launcher.side_effect = TestBisector.fake_create_launcher

        self.assertEqual(self.bisector.prepare_bisect()[1:],
            (expected_base, self.persist, expected_full_url))

if __name__ == '__main__':
    unittest.main()
