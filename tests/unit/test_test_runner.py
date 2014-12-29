#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import unittest
from mock import patch, Mock
import datetime

from mozregression.fetch_configs import create_config
from mozregression import test_runner

class TestManualTestRunner(unittest.TestCase):
    def setUp(self):
        fetch_config = create_config('firefox', 'linux', 64)
        fetch_config.set_nightly_repo('my-repo')
        fetch_config.set_inbound_branch('my-branch')
        self.runner = test_runner.ManualTestRunner(fetch_config)

    @patch('mozregression.test_runner.create_launcher')
    def test_nightly_create_launcher(self, create_launcher):
        launcher = Mock()
        create_launcher.return_value = launcher
        result_launcher = self.runner.create_launcher({
            'build_type': 'nightly',
            'build_date': datetime.date(2014, 12, 25),
            'build_url': 'http://my-url'
        })
        create_launcher.assert_called_with('firefox', 'http://my-url',
                                           persist_prefix='2014-12-25--my-repo--',
                                           persist=None)
        self.assertEqual(result_launcher, launcher)

    @patch('mozregression.test_runner.create_launcher')
    def test_inbound_create_launcher(self, create_launcher):
        launcher = Mock()
        create_launcher.return_value = launcher
        result_launcher = self.runner.create_launcher({
            'build_type': 'inbound',
            'timestamp': '123',
            'revision': '12345678',
            'build_url': 'http://my-url'
        })
        create_launcher.assert_called_with('firefox', 'http://my-url',
                                           persist_prefix='123--my-branch--',
                                           persist=None)
        self.assertEqual(result_launcher, launcher)

    @patch('__builtin__.raw_input')
    def test_get_verdict(self, raw_input):
        raw_input.return_value = 'g'
        verdict = self.runner.get_verdict({'build_type': 'inbound'})
        self.assertEqual(verdict, 'g')

    @patch('mozregression.test_runner.ManualTestRunner.create_launcher')
    @patch('mozregression.test_runner.ManualTestRunner.get_verdict')
    def test_evaluate(self, get_verdict, create_launcher):
        get_verdict.return_value = 'g'
        launcher = Mock()
        create_launcher.return_value = launcher
        build_infos = {'a':'b'}
        result = self.runner.evaluate(build_infos)

        create_launcher.assert_called_with(build_infos)
        launcher.get_app_info.assert_called_with()
        launcher.start.assert_called_with()
        get_verdict.assert_called_with(build_infos)
        launcher.stop.assert_called_with()
        self.assertEqual(result, 'g')
