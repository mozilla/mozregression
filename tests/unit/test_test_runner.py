#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import unittest
from mock import patch, Mock
import datetime

from mozregression import test_runner, errors


class TestManualTestRunner(unittest.TestCase):
    def setUp(self):
        self.runner = test_runner.ManualTestRunner()

    @patch('mozregression.test_runner.create_launcher')
    def test_nightly_create_launcher(self, create_launcher):
        launcher = Mock()
        create_launcher.return_value = launcher
        result_launcher = self.runner.create_launcher({
            'build_type': 'nightly',
            'build_date': datetime.date(2014, 12, 25),
            'build_url': 'http://my-url',
            'repo': 'my-repo',
            'app_name': 'firefox',
            'build_path': '/path/to',
        })
        create_launcher.\
            assert_called_with('firefox',
                               '/path/to')

        self.assertEqual(result_launcher, launcher)

    @patch('mozregression.download_manager.DownloadManager.download')
    @patch('mozregression.test_runner.create_launcher')
    def test_inbound_create_launcher(self, create_launcher, download):
        launcher = Mock()
        create_launcher.return_value = launcher
        result_launcher = self.runner.create_launcher({
            'build_type': 'inbound',
            'timestamp': '123',
            'revision': '12345678',
            'build_url': 'http://my-url',
            'repo': 'my-branch',
            'app_name': 'firefox',
            'build_path': '/path/to',
        })
        create_launcher.assert_called_with('firefox',
                                           '/path/to')
        self.assertEqual(result_launcher, launcher)

    @patch('__builtin__.raw_input')
    def test_get_verdict(self, raw_input):
        raw_input.return_value = 'g'
        verdict = self.runner.get_verdict({'build_type': 'inbound'}, False)
        self.assertEqual(verdict, 'g')

        output = raw_input.call_args[0][0]
        # bad is proposed
        self.assertIn('bad', output)
        # back is not
        self.assertNotIn('back', output)

    @patch('__builtin__.raw_input')
    def test_get_verdict_allow_back(self, raw_input):
        raw_input.return_value = 'back'
        verdict = self.runner.get_verdict({'build_type': 'inbound'}, True)
        output = raw_input.call_args[0][0]
        # back is now proposed
        self.assertIn('back', output)
        self.assertEqual(verdict, 'back')

    @patch('mozregression.test_runner.ManualTestRunner.create_launcher')
    @patch('mozregression.test_runner.ManualTestRunner.get_verdict')
    def test_evaluate(self, get_verdict, create_launcher):
        get_verdict.return_value = 'g'
        launcher = Mock()
        create_launcher.return_value = launcher
        build_infos = {'a': 'b'}
        result = self.runner.evaluate(build_infos)

        create_launcher.assert_called_with(build_infos)
        launcher.get_app_info.assert_called_with()
        launcher.start.assert_called_with()
        get_verdict.assert_called_with(build_infos, False)
        launcher.stop.assert_called_with()
        self.assertEqual(result[0], 'g')

    @patch('mozregression.test_runner.ManualTestRunner.create_launcher')
    @patch('mozregression.test_runner.ManualTestRunner.get_verdict')
    def test_evaluate_with_launcher_error_on_stop(self, get_verdict,
                                                  create_launcher):
        get_verdict.return_value = 'g'
        launcher = Mock(stop=Mock(side_effect=errors.LauncherError))
        create_launcher.return_value = launcher
        build_infos = {'a': 'b'}
        result = self.runner.evaluate(build_infos)

        # the LauncherError is silently ignore here
        launcher.stop.assert_called_with()
        self.assertEqual(result[0], 'g')


class TestCommandTestRunner(unittest.TestCase):
    def setUp(self):
        self.runner = test_runner.CommandTestRunner('my command')
        self.launcher = Mock()
        del self.launcher.binary  # block the auto attr binary on the mock

    def test_create(self):
        self.assertEqual(self.runner.command, 'my command')

    @patch('mozregression.test_runner.CommandTestRunner.create_launcher')
    @patch('subprocess.call')
    def evaluate(self, call, create_launcher, build_info={},
                 retcode=0, subprocess_call_effect=None):
        build_info['app_name'] = 'myapp'
        call.return_value = retcode
        if subprocess_call_effect:
            call.side_effect = subprocess_call_effect
        self.subprocess_call = call
        create_launcher.return_value = self.launcher
        return self.runner.evaluate(build_info)[0]

    def test_evaluate_retcode(self):
        self.assertEqual('g', self.evaluate(retcode=0))
        self.assertEqual('b', self.evaluate(retcode=1))

    def test_supbrocess_call(self):
        self.evaluate()
        command = self.subprocess_call.mock_calls[0][1][0]
        kwargs = self.subprocess_call.mock_calls[0][2]
        self.assertEqual(command, ['my', 'command'])
        self.assertIn('env', kwargs)

    def test_env_vars(self):
        self.evaluate(build_info={'my': 'var', 'int': 15})
        expected = {
            'MOZREGRESSION_MY': 'var',
            'MOZREGRESSION_INT': '15',
            'MOZREGRESSION_APP_NAME': 'myapp',
        }
        passed_env = self.subprocess_call.mock_calls[0][2]['env']
        self.assertTrue(set(expected).issubset(set(passed_env)))

    def test_command_placeholder_replaced(self):
        self.runner.command = 'run {app_name} "1"'
        self.evaluate()
        command = self.subprocess_call.mock_calls[0][1][0]
        self.assertEqual(command, ['run', 'myapp', '1'])

        self.runner.command = 'run \'{binary}\' "{foo}"'
        self.launcher.binary = 'mybinary'
        self.evaluate(build_info={'foo': 12})
        command = self.subprocess_call.mock_calls[0][1][0]
        self.assertEqual(command, ['run', 'mybinary', '12'])

    def test_command_placeholder_error(self):
        self.runner.command = 'run {app_nam} "1"'
        self.assertRaisesRegexp(errors.TestCommandError,
                                'formatting',
                                self.evaluate)

    def test_command_empty_error(self):
        # in case the command line is empty,
        # subprocess.call will raise IndexError
        self.assertRaisesRegexp(errors.TestCommandError,
                                'Empty', self.evaluate,
                                subprocess_call_effect=IndexError)

    def test_command_missing_error(self):
        # in case the command is missing or not executable,
        # subprocess.call will raise IOError
        self.assertRaisesRegexp(errors.TestCommandError,
                                'not found', self.evaluate,
                                subprocess_call_effect=OSError)
