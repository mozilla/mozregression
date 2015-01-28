#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import unittest
from mock import patch, Mock, call, MagicMock
import datetime

from mozregression.bisector import (BisectorHandler, NightlyHandler,
                                    InboundHandler, Bisector,
                                    BisectRunner)
from mozregression.main import parse_args
from mozregression import build_data

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
        self.assertEqual(self.handler.good_revision, '1')
        self.assertEqual(self.handler.bad_revision, '3')

    def test_get_pushlog_url(self):
        self.handler.found_repo = 'https://hg.mozilla.repo'
        self.handler.good_revision = '2'
        self.handler.bad_revision = '6'
        self.assertEqual(self.handler.get_pushlog_url(),
                         "https://hg.mozilla.repo/pushloghtml?fromchange=2&tochange=6")

    def test_print_range(self):
        self.handler.found_repo = 'https://hg.mozilla.repo'
        self.handler.good_revision = '2'
        self.handler.bad_revision = '6'
        log = []
        self.handler._logger = Mock(info = log.append)

        self.handler.print_range()
        self.assertEqual(log[0], "Last good revision: 2")
        self.assertEqual(log[1], "First bad revision: 6")
        self.assertIn(self.handler.get_pushlog_url(), log[2])

    @patch('mozregression.bisector.BisectorHandler._print_progress')
    def test_build_good(self, _print_progress):
        self.handler.build_good(0, [{"changeset": '123'}, {"changeset": '456'}])
        _print_progress.assert_called_with([{"changeset": '123'}, {"changeset": '456'}])

    @patch('mozregression.bisector.BisectorHandler._print_progress')
    def test_build_bad(self, _print_progress):
        # with at least two, _print_progress will be called
        self.handler.build_bad(0, [{"changeset": '123'}, {"changeset": '456'}])
        _print_progress.assert_called_with([{"changeset": '123'}, {"changeset": '456'}])

class TestNightlyHandler(unittest.TestCase):
    def setUp(self):
        self.handler = NightlyHandler()

    def test_build_infos(self):
        def get_associated_data(index):
            return index
        new_data = MagicMock(get_associated_data=get_associated_data)
        self.handler.set_build_data(new_data)
        result = self.handler.build_infos(1)
        self.assertEqual(result, {
            'build_type': 'nightly',
            'build_date': 1,
        })

    @patch('mozregression.bisector.BisectorHandler.initialize')
    def test_initialize(self, initialize):
        def get_associated_data(index):
            return index
        self.handler.build_data = Mock(get_associated_data=get_associated_data)
        self.handler.initialize()
        # check that members are set
        self.assertEqual(self.handler.good_date, 0)
        self.assertEqual(self.handler.bad_date, -1)

        initialize.assert_called_with(self.handler)

    def test_print_progress(self):
        log = []
        self.handler._logger = Mock(info = log.append)
        self.handler.good_date = datetime.date(2014, 11, 10)
        self.handler.bad_date = datetime.date(2014, 11, 20)
        def get_associated_data(index):
            if index == 0:
                return datetime.date(2014, 11, 15)
            elif index == -1:
                return datetime.date(2014, 11, 20)
        new_data = Mock(get_associated_data=get_associated_data)

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

    def test_print_range_without_repo(self):
        log = []
        self.handler._logger = Mock(info=log.append, error=log.append)
        self.handler.good_date = datetime.date(2014, 11, 10)
        self.handler.bad_date = datetime.date(2014, 11, 20)
        self.handler.print_range()
        self.assertIn("no pushlog url available", log[0])
        self.assertEqual('Newest known good nightly: 2014-11-10', log[1])
        self.assertEqual('Oldest known bad nightly: 2014-11-20', log[2])

    def test_print_range_rev_availables(self):
        self.handler.found_repo = 'https://hg.mozilla.repo'
        self.handler.good_revision = '2'
        self.handler.bad_revision = '6'
        log = []
        self.handler._logger = Mock(info=log.append)

        self.handler.print_range()
        self.assertEqual(log[0], "Last good revision: 2")
        self.assertEqual(log[1], "First bad revision: 6")
        self.assertIn(self.handler.get_pushlog_url(), log[2])

    def test_print_range_no_rev_availables(self):
        self.handler.found_repo = 'https://hg.mozilla.repo'
        self.handler.good_date = datetime.date(2014, 11, 10)
        self.handler.bad_date = datetime.date(2014, 11, 20)
        log = []
        self.handler._logger = Mock(info=log.append)

        self.handler.print_range()
        self.assertEqual('Newest known good nightly: 2014-11-10', log[0])
        self.assertEqual('Oldest known bad nightly: 2014-11-20', log[1])
        self.assertIn("pushloghtml?startdate=2014-11-10&enddate=2014-11-20", log[2])

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
        self.handler.good_revision = '3'
        self.handler.bad_revision = '1'
        self.handler.user_exit(0)
        self.assertEqual('Newest known good inbound revision: 3', log[0])
        self.assertEqual('Oldest known bad inbound revision: 1', log[1])

class MyBuildData(build_data.BuildData):
    def __init__(self, data=()):
        # init with a dict for value, as we assume that build_info is a dict
        # Just override setdefault to not use it here
        class MyDict(dict):
            def setdefault(self, key, value):
                pass
        build_data.BuildData.__init__(self, [MyDict({v:v}) for v in data])

    def _create_fetch_task(self, executor, i):
        ad = self.get_associated_data(i)
        return executor.submit(self._return_data, ad)

    def _return_data(self, data):
        return data

    def __repr__(self):
        # only useful when test fails
        return '[%s]' % ', '.join([str(self.get_associated_data(i).keys()[0])
                                   for i in range(len(self))])

    def __eq__(self, other):
        # for testing purpose, say that MyBuildData instances are equals
        # when there associated_data are equals.
        return [self.get_associated_data(i) for i in range(len(self))] \
            == [other.get_associated_data(i) for i in range(len(other))]

class TestBisector(unittest.TestCase):
    def setUp(self):
        self.handler = Mock(find_fix=False)
        self.test_runner = Mock()
        self.bisector = Bisector(Mock(), self.test_runner)

    def test__bisect_no_data(self):
        build_data = MyBuildData()
        result = self.bisector._bisect(self.handler, build_data)
        # test that handler methods where called
        self.handler.set_build_data.assert_called_with(build_data)
        self.handler.no_data.assert_called_once_with()
        # check return code
        self.assertEqual(result, Bisector.NO_DATA)

    def test__bisect_finished(self):
        build_data = MyBuildData([1])
        result = self.bisector._bisect(self.handler, build_data)
        # test that handler methods where called
        self.handler.set_build_data.assert_called_with(build_data)
        self.handler.finished.assert_called_once_with()
        # check return code
        self.assertEqual(result, Bisector.FINISHED)

    def do__bisect(self, build_data, verdicts):
        iter_verdict = iter(verdicts)
        def evaluate(build_info, allow_back=False):
            return iter_verdict.next(), {
                'application_changeset': 'unused',
                'application_repository': 'unused'
            }
        self.test_runner.evaluate = Mock(side_effect=evaluate)
        result = self.bisector._bisect(self.handler, build_data)
        return {
            'result': result,
        }

    def test__bisect_case1(self):
        test_result = self.do__bisect(MyBuildData([1, 2, 3, 4, 5]), ['g', 'b'])
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

    def test__bisect_case1_hunt_fix(self):
        self.handler.find_fix = True
        test_result = self.do__bisect(MyBuildData([1, 2, 3, 4, 5]), ['g', 'b'])
        # check that set_build_data was called
        self.handler.set_build_data.assert_has_calls([
            # first call
            call(MyBuildData([1, 2, 3, 4, 5])),
            # we answered good
            call(MyBuildData([1, 2, 3])),
            # we answered bad
            call(MyBuildData([2, 3])),
        ])
        # ensure that we called the handler's methods
        self.assertEqual(self.handler.initialize.mock_calls, [call()]*3)
        self.handler.build_good.assert_called_once_with(2, MyBuildData([1, 2, 3]))
        self.handler.build_bad.assert_called_once_with(1, MyBuildData([2, 3]))
        # bisection is finished
        self.assertEqual(test_result['result'], Bisector.FINISHED)

    def test__bisect_case2(self):
        test_result = self.do__bisect(MyBuildData([1, 2, 3]), ['r', 's'])
        # check that set_build_data was called
        self.handler.set_build_data.assert_has_calls([
            # first call
            call(MyBuildData([1, 2, 3])),
            # we asked for a retry
            call(MyBuildData([1, 2, 3])),
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

    def test__bisect_with_back(self):
        test_result = self.do__bisect(MyBuildData([1, 2, 3, 4, 5]), ['g', 'back', 'b', 'g'])
        # check that set_build_data was called
        self.handler.set_build_data.assert_has_calls([
            # first call
            call(MyBuildData([1, 2, 3, 4, 5])),
            # we answered good
            call(MyBuildData([3, 4, 5])),
            # oups! let's go back
            call(MyBuildData([1, 2, 3, 4, 5])),
            # we answered bad this time
            call(MyBuildData([1, 2, 3])),
            # then good
            call(MyBuildData([2, 3])),
        ])
        # bisection is finished
        self.assertEqual(test_result['result'], Bisector.FINISHED)

    def test__bisect_user_exit(self):
        test_result = self.do__bisect(MyBuildData(range(20)), ['e'])
        # check that set_build_data was called
        self.handler.set_build_data.assert_has_calls([call(MyBuildData(range(20)))])
        # ensure that we called the handler's method
        self.handler.initialize.assert_called_once_with()
        self.handler.user_exit.assert_called_with(10)
        # user exit
        self.assertEqual(test_result['result'], Bisector.USER_EXIT)

    @patch('mozregression.bisector.Bisector._bisect')
    def test_bisect(self, _bisect):
        _bisect.return_value = 1
        build_data = Mock()
        build_data_class = Mock(return_value=build_data)
        self.handler.build_data_class = build_data_class
        result = self.bisector.bisect(self.handler, 'g', 'b', s=1)
        build_data_class.assert_called_with(self.bisector.fetch_config,
                                            'g', 'b', s=1)
        self.assertFalse(build_data.reverse.called)
        _bisect.assert_called_with(self.handler, build_data)
        self.assertEqual(result, 1)

    @patch('mozregression.bisector.Bisector._bisect')
    def test_bisect_reverse(self, _bisect):
        build_data = Mock()
        build_data_class = Mock(return_value=build_data)
        self.handler.build_data_class = build_data_class
        self.handler.find_fix = True
        self.bisector.bisect(self.handler, 'g', 'b', s=1)
        build_data_class.assert_called_with(self.bisector.fetch_config,
                                            'b', 'g', s=1)
        _bisect.assert_called_with(self.handler, build_data)

class TestBisectRunner(unittest.TestCase):
    @patch('mozregression.bisector.get_default_logger')
    def setUp(self, get_default_logger):
        self.fetch_config = Mock()
        self.test_runner = Mock()
        self.logger = Mock()
        self.logs = []
        get_default_logger.return_value = Mock(info=self.logs.append)
        self.brunner = BisectRunner(self.fetch_config, self.test_runner, parse_args([]))

    def test_create(self):
        self.assertIsInstance(self.brunner.bisector, Bisector)

    def print_resume_info(self, handler_klass, **kwargs):
        # print_resume_info require some handlers attribute
        handler = handler_klass()
        if isinstance(handler, NightlyHandler):
            handler.good_date = datetime.date(2015, 1, 1)
            handler.bad_date = datetime.date(2015, 1, 11)
        else:
            handler.good_revision = '123'
            handler.bad_revision = '456'

        for k, v in kwargs.iteritems():
            setattr(self.brunner.options, k, v)
        self.brunner.print_resume_info(handler)
        return self.logs[-1]

    def test_print_resume_infos_nightly(self):
        result = self.print_resume_info(NightlyHandler, bits=64)
        self.assertIn('--bits=64', result)
        self.assertIn('--good=2015-01-01', result)
        self.assertIn('--bad=2015-01-11', result)
        self.assertNotIn('--inbound', result)

        self.assertNotIn('--find-fix', result)
        result = self.print_resume_info(NightlyHandler, find_fix=True)
        self.assertIn('--find-fix', result)

        self.assertNotIn('--addon', result)
        result = self.print_resume_info(NightlyHandler, addons=['1', '2'])
        self.assertIn('--addon=1 --addon=2', result)

        self.assertNotIn('--profile', result)
        result = self.print_resume_info(NightlyHandler, profile='profile')
        self.assertIn('--profile=profile', result)

        self.assertNotIn('--inbound-branch', result)
        result = self.print_resume_info(NightlyHandler, inbound_branch='i')
        self.assertIn('--inbound-branch=i', result)

        self.assertNotIn('--repo', result)
        result = self.print_resume_info(NightlyHandler, repo='r')
        self.assertIn('--repo=r', result)

        self.assertNotIn('--persist', result)
        result = self.print_resume_info(NightlyHandler, persist='/tmp')
        self.assertIn('--persist=/tmp', result)

        self.assertNotIn('--arg', result)
        result = self.print_resume_info(NightlyHandler, cmdargs=['1', '2'])
        self.assertIn('--arg=1 --arg=2', result)

    def test_print_resume_infos_inbound(self):
        result = self.print_resume_info(InboundHandler, bits=32, app='b2g')
        self.assertIn('--bits=32', result)
        self.assertIn('--app=b2g', result)
        self.assertIn('--good-rev=123', result)
        self.assertIn('--bad-rev=456', result)
        self.assertIn('--inbound', result)


if __name__ == '__main__':
    unittest.main()
