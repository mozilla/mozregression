#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import unittest
from mock import patch, Mock, call
import datetime

from mozregression.fetch_configs import create_config
from mozregression.bisector import (BisectorHandler, NightlyHandler,
                                    InboundHandler, Bisector)

class TestBisectorHandler(unittest.TestCase):
    def setUp(self):
        self.handler = BisectorHandler(create_config('firefox', 'linux', 64))
        self.handler.set_build_data([
            {'build_url': 'http://build_url_0'}
        ])

    def test_initialize(self):
        self.handler.set_build_data([
            {'changeset': '1', 'repository': 'my'},
            {},
            {'changeset': '3', 'repository': 'my'},
        ])
        self.handler.initialize()
        self.assertEqual(self.handler.found_repo, 'my')
        self.assertEqual(self.handler.last_good_revision, '1')
        self.assertEqual(self.handler.first_bad_revision, '3')

    @patch('mozregression.bisector.BisectorHandler.launcher_persist_prefix')
    @patch('mozregression.bisector.create_launcher')
    def test_start_launcher(self, create_launcher, launcher_persist_prefix):
        app_info = {'application_repository': 'something'}
        launcher = Mock(get_app_info=Mock(return_value=app_info))
        create_launcher.return_value = launcher
        launcher_persist_prefix.return_value = 'something-'

        result = self.handler.start_launcher(0)
        # create launcher is well called
        create_launcher.assert_called_with('firefox', 'http://build_url_0',
                                           persist=None,
                                           persist_prefix='something-')
        # launcher is started
        launcher.start.assert_called_with(**self.handler.launcher_kwargs)
        # app_info and found_repo are set
        self.assertEqual(self.handler.app_info, app_info)
        self.assertEqual(self.handler.found_repo, 'something')
        # and launvher instance is returned
        self.assertEqual(result, launcher)

    def test_get_pushlog_url(self):
        self.handler.found_repo = 'https://hg.mozilla.repo'
        self.handler.last_good_revision = '2'
        self.handler.first_bad_revision = '6'
        self.assertEqual(self.handler.get_pushlog_url(),
                         "https://hg.mozilla.repo/pushloghtml?fromchange=2&tochange=6")

    def test_print_range(self):
        self.handler.found_repo = 'https://hg.mozilla.repo'
        self.handler.last_good_revision = '2'
        self.handler.first_bad_revision = '6'
        log = []
        self.handler._logger = Mock(info = log.append)

        self.handler.print_range()
        self.assertEqual(log[0], "Last good revision: 2")
        self.assertEqual(log[1], "First bad revision: 6")
        self.assertIn(self.handler.get_pushlog_url(), log[2])

    @patch('mozregression.bisector.BisectorHandler._print_progress')
    def test_build_good(self, _print_progress):
        self.handler.app_info = {"application_changeset": '123'}
        # call build_good with no new data points
        self.handler.build_good(0, [])
        self.assertEqual(self.handler.last_good_revision, '123')
        _print_progress.assert_not_called()
        # with at least two, _print_progress will be called
        self.handler.build_good(0, [1, 2])
        _print_progress.assert_called_with([1, 2])

    @patch('mozregression.bisector.BisectorHandler._print_progress')
    def test_build_bad(self, _print_progress):
        self.handler.app_info = {"application_changeset": '123'}
        # call build_bad with no new data points
        self.handler.build_bad(0, [])
        self.assertEqual(self.handler.first_bad_revision, '123')
        _print_progress.assert_not_called()
        # with at least two, _print_progress will be called
        self.handler.build_bad(0, [1, 2])
        _print_progress.assert_called_with([1, 2])

class TestNightlyHandler(unittest.TestCase):
    def setUp(self):
        self.handler = NightlyHandler(create_config('firefox', 'linux', 64))

    def test_launcher_persist_prefix(self):
        # define a repo and a mid_date
        self.handler.fetch_config.set_nightly_repo('myrepo')
        self.handler.mid_date = datetime.date(2014, 11, 10)

        prefix = self.handler.launcher_persist_prefix(1)
        self.assertEqual(prefix, '2014-11-10--myrepo--')

    @patch('mozregression.bisector.NightlyHandler.launcher_persist_prefix')
    @patch('mozregression.bisector.BisectorHandler.start_launcher')
    def test_start_launcher(self, start_launcher, launcher_persist_prefix):
        get_date_for_index = Mock(side_effect=lambda i: i)
        self.handler.build_data = Mock(get_date_for_index=get_date_for_index)
        start_launcher.return_value = 'my_launcher'

        launcher = self.handler.start_launcher(3)
        # check we have called get_date_for_index
        get_date_for_index.assert_has_calls([call(0), call(3), call(-1)],
                                            any_order=True)
        #  dates are well set
        self.assertEqual(self.handler.mid_date, 3)
        self.assertEqual(self.handler.good_date, 0)
        self.assertEqual(self.handler.bad_date, -1)
        # base BisectorHandler.start_launcher has been called and is returned
        start_launcher.assert_called_with(self.handler, 3)
        self.assertEqual(launcher, 'my_launcher')

    def test_print_progress(self):
        log = []
        self.handler._logger = Mock(info = log.append)
        self.handler.good_date = datetime.date(2014, 11, 10)
        self.handler.bad_date = datetime.date(2014, 11, 20)
        def get_date_for_index(index):
            if index == 0:
                return datetime.date(2014, 11, 15)
            elif index == -1:
                return datetime.date(2014, 11, 20)
        new_data = Mock(get_date_for_index=get_date_for_index)

        self.handler._print_progress(new_data)
        self.assertIn('from [2014-11-10, 2014-11-20] (10 days)', log[0])
        self.assertIn('to [2014-11-15, 2014-11-20] (5 days)', log[0])
        self.assertIn('2 steps left', log[0])

class TestInboundHandler(unittest.TestCase):
    def setUp(self):
        self.handler = InboundHandler(create_config('firefox', 'linux', 64))

    def test_launcher_persist_prefix(self):
        # define a repo and a mid_date
        self.handler.fetch_config.set_inbound_branch('mybranch')
        self.handler.set_build_data([{'timestamp': 123456789}])

        prefix = self.handler.launcher_persist_prefix(0)
        self.assertEqual(prefix, '123456789--mybranch--')

    @patch('mozregression.bisector.NightlyHandler.launcher_persist_prefix')
    @patch('mozregression.bisector.BisectorHandler.start_launcher')
    def test_start_launcher(self, start_launcher, launcher_persist_prefix):
        start_launcher.return_value = 'my_launcher'
        self.handler.set_build_data([{'timestamp': 123456789, 'revision':'12'}])
        launcher = self.handler.start_launcher(0)

        # base BisectorHandler.start_launcher has been called and is returned
        start_launcher.assert_called_with(self.handler, 0)
        self.assertEqual(launcher, 'my_launcher')

    def test_print_progress(self):
        log = []
        self.handler._logger = Mock(info = log.append)
        self.handler.set_build_data([
            {'revision':'12'},
            {'revision':'123'},
            {'revision':'1234'},
            {'revision':'12345'},
        ])
        new_data = [{'revision': '1234'}, {'revision': '12345'}]

        self.handler._print_progress(new_data)
        self.assertIn('from [12, 12345] (4 revisions)', log[0])
        self.assertIn('to [1234, 12345] (2 revisions)', log[0])
        self.assertIn('1 steps left', log[0])

class MyBuildData(list):
    ensure_limits_called = False
    def mid_point(self):
        if len(self) < 3:
            return 0
        return len(self) / 2

    def ensure_limits(self):
        self.ensure_limits_called = True

    def __getslice__(self, smin, smax):
        return MyBuildData(list.__getslice__(self, smin, smax))

class TestBisector(unittest.TestCase):
    def setUp(self):
        self.handler = Mock()
        self.bisector = Bisector(self.handler)

    @patch('__builtin__.raw_input')
    def test_get_verdict(self, raw_input):
        raw_input.return_value = 'g'
        verdict = self.bisector.get_verdict()
        self.assertEqual(verdict, 'g')

    def test_bisect_no_data(self):
        build_data = MyBuildData()
        result = self.bisector.bisect(build_data)
        # test that handler methods where called
        self.handler.set_build_data.assert_called_with(build_data)
        self.handler.no_data.assert_called_once_with()
        # check return code
        self.assertEqual(result, Bisector.NO_DATA)

    def test_bisect_finished(self):
        build_data = MyBuildData([1])
        result = self.bisector.bisect(build_data)
        # test that handler methods where called
        self.handler.set_build_data.assert_called_with(build_data)
        self.handler.finished.assert_called_once_with()
        # check return code
        self.assertEqual(result, Bisector.FINISHED)

    def do_bisect(self, build_data, verdicts):
        iter_verdict = iter(verdicts)
        self.bisector.get_verdict = Mock(side_effect=iter_verdict.next)
        launcher = Mock()
        self.handler.start_launcher.return_value = launcher
        result = self.bisector.bisect(build_data)
        return {
            'result': result,
            'launcher': launcher,
        }

    def test_bisect_case1(self):
        test_result = self.do_bisect(MyBuildData([1, 2, 3, 4, 5]), ['g', 'b'])
        # check that set_build_data was called
        self.handler.set_build_data.assert_has_calls([
            # first call
            call(MyBuildData([1, 2, 3, 4, 5])),
            # we answered good
            call(MyBuildData([3, 4, 5])),
            # we answered bad
            call(MyBuildData([3, 4])),
        ])
        # ensure that the launcher was stopped
        test_result['launcher'].stop.assert_called_with()
        # ensure that we called the handler's methods
        self.handler.initialize.assert_called_with()
        self.handler.build_good.assert_called_with(2, MyBuildData([3, 4, 5]))
        self.handler.build_bad.assert_called_with(1, MyBuildData([3, 4]))
        self.assertTrue(self.handler.build_data.ensure_limits_called)
        # bisection is finished
        self.assertEqual(test_result['result'], Bisector.FINISHED)

    def test_bisect_case2(self):
        test_result = self.do_bisect(MyBuildData([1, 2, 3]), ['r', 's'])
        # check that set_build_data was called
        self.handler.set_build_data.assert_has_calls([
            # first call
            # this should be call(MyBuildData([1, 2, 3])),
            # but as the code delete the index in place when we skip
            # (with a del statement) our build_data is impacted.
            # well, we just have to know that for the test.
            call(MyBuildData([1, 3])),
            # we asked for a retry (same comment as above)
            call(MyBuildData([1, 3])),
            # we skipped one
            call(MyBuildData([1, 3])),
        ])
        # ensure that the launcher was stopped
        test_result['launcher'].stop.assert_called_with()
        # ensure that we called the handler's methods
        self.handler.initialize.assert_called_with()
        self.handler.build_retry.assert_called_with(1)
        self.handler.build_skip.assert_called_with(1)
        self.assertTrue(self.handler.build_data.ensure_limits_called)
        # bisection is finished
        self.assertEqual(test_result['result'], Bisector.FINISHED)

    def test_bisect_user_exit(self):
        test_result = self.do_bisect(MyBuildData(range(20)), ['e'])
        # check that set_build_data was called
        self.handler.set_build_data.assert_has_calls([call(MyBuildData(range(20)))])
        # ensure that we called the handler's method
        self.handler.initialize.assert_called_once_with()
        self.handler.user_exit.assert_called_with(10)
        # user exit
        self.assertEqual(test_result['result'], Bisector.USER_EXIT)

if __name__ == '__main__':
    unittest.main()
