#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import unittest
import datetime
from mock import patch, Mock
import requests

from mozregression import main, errors, __version__


class TestResumeInfoBisectRunner(unittest.TestCase):
    def setUp(self):
        self.opts = Mock(persist=None)

    @patch('mozregression.main.BisectRunner')
    def test_do_bisect(self, BisectRunner):
        BisectRunner.do_bisect.return_value = 0
        runner = main.ResumeInfoBisectRunner(None, None, self.opts)
        result = runner.do_bisect('handler', 'g', 'b', range=4)

        self.assertEquals(result, 0)
        BisectRunner.do_bisect.assert_called_with(runner, 'handler', 'g', 'b',
                                                  range=4)

    @patch('atexit.register')
    @patch('mozregression.main.BisectRunner')
    def test_do_bisect_error(self, BisectRunner, register):
        BisectRunner.do_bisect.side_effect = KeyboardInterrupt
        runner = main.ResumeInfoBisectRunner(None, None, self.opts)
        handler = Mock(good_revision=1, bad_revision=2)
        with self.assertRaises(KeyboardInterrupt):
            runner.do_bisect(handler, 'g', 'b')

        register.assert_called_with(runner.on_exit_print_resume_info,
                                    handler)

    @patch('mozregression.main.BisectRunner')
    def test_on_exit_print_resume_info(self, BisectRunner):
        handler = Mock()
        runner = main.ResumeInfoBisectRunner(None, None, self.opts)
        runner.print_resume_info = Mock()
        runner.on_exit_print_resume_info(handler)

        handler.print_range.assert_called_with()
        runner.print_resume_info.assert_called_with(handler)


class TestCheckMozregresionVersion(unittest.TestCase):
    @patch('requests.get')
    def test_version_is_upto_date(self, get):
        logger = Mock()
        response = Mock(json=lambda: {'info': {'version':  __version__}})
        get.return_value = response
        main.check_mozregression_version(logger)
        self.assertFalse(logger.critical.called)

    @patch('requests.get')
    def test_Exception_error(self, get):
        logger = Mock()
        get.side_effect = requests.RequestException
        # exception is handled inside main.check_mozregression_version
        main.check_mozregression_version(logger)
        self.assertRaises(requests.RequestException, get)

    @patch('requests.get')
    def test_warn_if_version_is_not_up_to_date(self, get):
        logger = Mock()
        response = Mock(json=lambda: {'info': {'version': 0}})
        get.return_value = response
        main.check_mozregression_version(logger)
        self.assertEqual(logger.warning.call_count, 2)


class TestMain(unittest.TestCase):
    def setUp(self):
        self.runner = Mock()
        self.logger = Mock()

    @patch('mozregression.main.check_mozregression_version')
    @patch('mozlog.structured.commandline.setup_logging')
    @patch('mozregression.main.set_http_session')
    @patch('mozregression.main.ResumeInfoBisectRunner')
    def do_cli(self, argv, BisectRunner, set_http_session,
               setup_logging, check_mozregression_version):
        setup_logging.return_value = self.logger

        def create_runner(fetch_config, test_runner, options):
            self.runner.fetch_config = fetch_config
            self.runner.test_runner = test_runner
            self.runner.options = options
            return self.runner
        BisectRunner.side_effect = create_runner
        try:
            main.main(argv)
        except SystemExit as exc:
            return exc.code
        else:
            self.fail('mozregression.main.cli did not call sys.exit')

    def pop_logs(self):
        logs = []
        for i in range(len(self.logger.mock_calls)):
            call = self.logger.mock_calls.pop(0)
            logs.append((call[0], call[1][0]))
        return logs

    def pop_exit_error_msg(self):
        for lvl, msg in reversed(self.pop_logs()):
            if lvl == 'error':
                return msg

    def test_without_args(self):
        self.runner.bisect_nightlies.return_value = 0
        exitcode = self.do_cli([])
        # bisect_nightlies has been called
        self.runner.bisect_nightlies.assert_called_with(datetime.date(2009,
                                                                      1, 1),
                                                        datetime.date.today())
        # we exited with the return value of bisect_nightlies
        self.assertEquals(exitcode, 0)

    def test_bisect_inbounds(self):
        self.runner.bisect_inbound.return_value = 0
        exitcode = self.do_cli(['--good-rev=1', '--bad-rev=5'])
        self.assertEqual(exitcode, 0)
        self.runner.bisect_inbound.assert_called_with('1', '5')

    def test_handle_keyboard_interrupt(self):
        # KeyboardInterrupt is handled with a nice error message.
        self.runner.bisect_nightlies.side_effect = KeyboardInterrupt
        exitcode = self.do_cli([])
        self.assertIn('Interrupted', exitcode)

    def test_handle_mozregression_errors(self):
        # Any MozRegressionError subclass is handled with a nice error message
        self.runner.bisect_nightlies.side_effect = \
            errors.MozRegressionError('my error')
        exitcode = self.do_cli([])
        self.assertNotEqual(exitcode, 0)
        self.assertIn('my error', self.pop_exit_error_msg())

    def test_handle_other_errors(self):
        # other exceptions are just thrown as usual
        # so we have complete stacktrace
        self.runner.bisect_nightlies.side_effect = NameError
        self.assertRaises(NameError, self.do_cli, [])
