#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import unittest
from mock import patch, Mock, call, MagicMock
import datetime

from mozregression.bisector import (BisectorHandler, NightlyHandler,
                                    InboundHandler, Bisector)

class TestBisectorHandler(unittest.TestCase):
    def setUp(self):
        self.handler = BisectorHandler()
        self.handler.set_build_data([
            {'build_url': 'http://build_url_0', 'repository': 'my'}
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
        self.handler.build_good(0, [{"changeset": '123'}, {"changeset": '456'}])
        self.assertEqual(self.handler.last_good_revision, '123')
        _print_progress.assert_called_with([{"changeset": '123'}, {"changeset": '456'}])

    @patch('mozregression.bisector.BisectorHandler._print_progress')
    def test_build_bad(self, _print_progress):
        # with at least two, _print_progress will be called
        self.handler.build_bad(0, [{"changeset": '123'}, {"changeset": '456'}])
        self.assertEqual(self.handler.first_bad_revision, '456')
        _print_progress.assert_called_with([{"changeset": '123'}, {"changeset": '456'}])

class TestNightlyHandler(unittest.TestCase):
    def setUp(self):
        self.handler = NightlyHandler()

    def test_build_infos(self):
        def get_date_for_index(index):
            return index
        new_data = MagicMock(get_date_for_index=get_date_for_index)
        self.handler.set_build_data(new_data)
        result = self.handler.build_infos(1)
        self.assertEqual(result, {
            'build_type': 'nightly',
            'build_date': 1,
        })
        # check that members are set
        self.assertEqual(self.handler.good_date, 0)
        self.assertEqual(self.handler.mid_date, 1)
        self.assertEqual(self.handler.bad_date, -1)

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

    def test_user_exit(self):
        log = []
        self.handler._logger = Mock(info = log.append)
        self.handler.good_date = datetime.date(2014, 11, 10)
        self.handler.bad_date = datetime.date(2014, 11, 20)
        self.handler.user_exit(0)
        self.assertEqual('Newest known good nightly: 2014-11-10', log[0])
        self.assertEqual('Oldest known bad nightly: 2014-11-20', log[1])

class TestInboundHandler(unittest.TestCase):
    def setUp(self):
        self.handler = InboundHandler()

    def test_build_infos(self):
        self.handler.set_build_data([{'changeset': '1', 'repository': 'my'}])
        result = self.handler.build_infos(0)
        self.assertEqual(result, {
            'changeset': '1',
            'repository': 'my',
            'build_type': 'inbound'
        })

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

    def test_user_exit(self):
        log = []
        self.handler._logger = Mock(info = log.append)
        self.handler.last_good_revision = '3'
        self.handler.first_bad_revision = '1'
        self.handler.user_exit(0)
        self.assertEqual('Newest known good inbound revision: 3', log[0])
        self.assertEqual('Oldest known bad inbound revision: 1', log[1])

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
        self.test_runner = Mock()
        self.bisector = Bisector(self.handler, self.test_runner)

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
        def evaluate(build_info):
            return iter_verdict.next()
        self.test_runner.evaluate = Mock(side_effect=evaluate)
        result = self.bisector.bisect(build_data)
        return {
            'result': result,
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
