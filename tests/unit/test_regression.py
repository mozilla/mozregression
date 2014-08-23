import unittest
from mock import patch, Mock
import datetime
import tempfile
import shutil
import os
import requests
from mozregression.regression import get_app, Bisector, get_default_dates
from mozregression import utils

class TestRegression(unittest.TestCase):
    def setUp(self):
        self.addCleanup(utils.set_http_cache_session, None)

    def verity_options(self, bisector, bad_date, good_date, app='firefox'):
        self.assertEquals(bisector.options.app, app)
        self.assertEquals(bisector.options.bad_date, bad_date)
        self.assertEquals(bisector.options.good_date, good_date)

    @patch('sys.argv')
    def test_get_app(self, argv):
        argv = ['mozregression',]
        actual = get_app()
        actual_self = actual.__self__
        self.assertTrue(isinstance(actual_self, Bisector))

        # default dates are used with empty args
        (bad_date, good_date) = get_default_dates()
        self.verity_options(actual_self, bad_date, good_date)

        # default is to use a cache session
        a_session = utils.get_http_session()
        self.assertTrue(isinstance(a_session, requests.Session))
