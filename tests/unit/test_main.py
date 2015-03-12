#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import unittest
from mock import patch, Mock
import datetime
import tempfile
import os
import requests

from mozregression import main, utils, errors
from mozregression.test_runner import CommandTestRunner
from mozregression import __version__


class TestMainCli(unittest.TestCase):
    def setUp(self):
        self.runner = Mock()

    @patch('mozregression.main.check_mozregression_version')
    @patch('mozregression.main.get_defaults')
    @patch('mozlog.structured.commandline.setup_logging')
    @patch('mozregression.main.set_http_cache_session')
    @patch('mozregression.limitedfilecache.get_cache')
    @patch('mozregression.main.ResumeInfoBisectRunner')
    def do_cli(self, argv, BisectRunner, get_cache, set_http_cache_session,
               setup_logging, get_defaults, check_mozregression_version):
        get_defaults.return_value = dict()

        def create_runner(fetch_config, test_runner, options):
            self.runner.fetch_config = fetch_config
            self.runner.test_runner = test_runner
            self.runner.options = options
            return self.runner
        BisectRunner.side_effect = create_runner
        try:
            main.cli(argv)
        except SystemExit as exc:
            return exc.code
        else:
            self.fail('mozregression.main.cli did not call sys.exit')

    @patch('sys.stdout')
    def test_get_usage(self, stdout):
        output = []
        stdout.write.side_effect = output.append

        exitcode = self.do_cli(['-h'])
        output = ''.join(output)
        self.assertEqual(exitcode, 0)
        self.assertIn('usage:', output)

    def test_get_erronous_cfg_defaults(self):
        handle, filepath = tempfile.mkstemp()
        self.addCleanup(os.unlink, filepath)

        with os.fdopen(handle, 'w') as conf_file:
            conf_file.write('aaaaaaaaaaa [Defaults]\n')

        with self.assertRaises(SystemExit):
            main.get_defaults(filepath)

    def test_get_defaults(self):
        valid_values = {'http-timeout': '10.2',
                        'http-cache-dir': '/home/foo/.mozregression',
                        'bits': '64'}

        handle, filepath = tempfile.mkstemp()
        conf_default = main.DEFAULT_CONF_FNAME

        self.addCleanup(os.unlink, filepath)
        self.addCleanup(setattr, main, "DEFAULT_CONF_FNAME", conf_default)

        main.DEFAULT_CONF_FNAME = filepath

        with os.fdopen(handle, 'w') as conf_file:
            conf_file.write('[Defaults]\n')
            for key, value in valid_values.iteritems():
                conf_file.write("%s=%s\n" % (key, value))

        options = main.parse_args(['--bits=32'])

        self.assertEqual(options.http_timeout, 10.2)
        self.assertEqual(options.http_cache_dir, '/home/foo/.mozregression')
        self.assertEqual(options.bits, 32)

    def test_without_args(self):
        self.runner.bisect_nightlies.return_value = 0
        exitcode = self.do_cli([])
        # application is by default firefox
        self.assertEqual(self.runner.fetch_config.app_name,
                         'firefox')
        # bisect_nightlies has been called
        self.runner.bisect_nightlies.assert_called_with(datetime.date(2009,
                                                                      1, 1),
                                                        datetime.date.today())
        # we exited with the return value of bisect_nightlies
        self.assertEquals(exitcode, 0)

    def test_basic_inbound(self):
        self.runner.bisect_inbound.return_value = 0
        exitcode = self.do_cli(['--good-rev=1', '--bad-rev=5'])
        # application is by default firefox
        self.assertEqual(self.runner.fetch_config.app_name, 'firefox')
        # bisect_inbound has been called
        self.runner.bisect_inbound.assert_called_with('1', '5')
        # we exited with the return value of bisect_inbound
        self.assertEquals(exitcode, 0)

    def test_inbound_revs_must_be_given(self):
        argslist = [
            ['--good-rev=1'], ['--bad-rev=5'],
        ]
        for args in argslist:
            exitcode = self.do_cli(args)
            self.assertIn('--good-rev and --bad-rev must be set', exitcode)

    @patch('mozregression.fetch_configs.FirefoxConfig.is_inbound')
    def test_inbound_must_be_doable(self, is_inbound):
        is_inbound.return_value = False
        exitcode = self.do_cli(['--good-rev=1', '--bad-rev=5'])
        self.assertIn('Unable to bissect inbound', exitcode)

    @patch('mozregression.main.formatted_valid_release_dates')
    def test_list_releases(self, formatted_valid_release_dates):
        exitcode = self.do_cli(['--list-releases'])
        formatted_valid_release_dates.assert_called_once_with()
        self.assertIn(exitcode, (0, None))

    def test_bad_date_and_bad_release_are_incompatible(self):
        exitcode = self.do_cli(['--bad=2014-11-10', '--bad-release=1'])
        self.assertIn('incompatible', exitcode)

    def test_bad_release_invalid(self):
        exitcode = self.do_cli(['--bad-release=-1'])
        self.assertIn('Unable to find a matching date for release', exitcode)

    def test_good_date_and_good_release_are_incompatible(self):
        exitcode = self.do_cli(['--good=2014-11-10', '--good-release=1'])
        self.assertIn('incompatible', exitcode)

    def test_good_release_invalid(self):
        exitcode = self.do_cli(['--good-release=-1'])
        self.assertIn('Unable to find a matching date for release', exitcode)

    def test_handle_keyboard_interrupt(self):
        # KeyboardInterrupt are handled with a nice error message.
        self.runner.bisect_nightlies.side_effect = KeyboardInterrupt
        exitcode = self.do_cli([])
        self.assertIn('Interrupted', exitcode)

    def test_handle_mozregression_errors(self):
        # Any MozRegressionError subclass is handled with a nice error message
        self.runner.bisect_nightlies.side_effect = \
            errors.MozRegressionError('my error')
        exitcode = self.do_cli([])
        self.assertIn('my error', exitcode)

    def test_handle_other_errors(self):
        # other exceptions are just thrown as usual
        # so we have complete stacktrace
        self.runner.bisect_nightlies.side_effect = NameError
        self.assertRaises(NameError, self.do_cli, [])

    def test_bisect_nightlies_with_find_fix_proposal(self):
        exitcode = self.do_cli(['--bad=2015-01-06', '--good=2015-01-21'])
        self.assertIn('--find-fix flag', exitcode)

    def test_bisect_nightlies_with_find_fix_bad_usage(self):
        exitcode = self.do_cli(['--good=2015-01-06',
                                '--bad=2015-01-21',
                                '--find-fix'])
        self.assertIn('not use the --find-fix flag', exitcode)

    def test_commad_make_use_of_commandtestrunner(self):
        self.do_cli(['--command=my command'])
        self.assertIsInstance(self.runner.test_runner, CommandTestRunner)

    def test_releases_to_dates(self):
        releases = sorted(utils.releases().items(), key=lambda v: v[0])
        good = releases[0]
        bad = releases[-1]
        self.do_cli(['--good-release=%s' % good[0],
                     '--bad-release=%s' % bad[0]])

        self.runner.bisect_nightlies.\
            assert_called_with(utils.parse_date(good[1]),
                               utils.parse_date(bad[1]))

    def test_download_in_background_is_on_by_default(self):
        self.do_cli([])
        self.assertTrue(self.runner.options.background_dl)

    def test_deactive_download_in_background(self):
        self.do_cli(['--no-background-dl'])
        self.assertFalse(self.runner.options.background_dl)


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


class TestPreference(unittest.TestCase):
    def test_preference_file(self):
        handle, filepath = tempfile.mkstemp()
        self.addCleanup(os.unlink, filepath)

        with os.fdopen(handle, 'w') as conf_file:
            conf_file.write('{ "browser.tabs.remote.autostart": false }')

        prefs_files = [filepath]
        prefs = main.preference(prefs_files, None)
        self.assertEqual(prefs, [('browser.tabs.remote.autostart', False)])

    def test_preference_args(self):
        prefs_args = ["browser.tabs.remote.autostart:false"]

        prefs = main.preference(None, prefs_args)
        self.assertEqual(prefs, [('browser.tabs.remote.autostart', False)])

        prefs_args = ["browser.tabs.remote.autostart"]

        prefs = main.preference(None, prefs_args)
        self.assertEquals(len(prefs), 0)


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

if __name__ == '__main__':
    unittest.main()
