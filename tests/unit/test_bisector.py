from __future__ import absolute_import

import datetime
import unittest

from mock import MagicMock, Mock, call, patch

from mozregression import build_range
from mozregression.bisector import (
    Bisection,
    Bisector,
    BisectorHandler,
    IntegrationHandler,
    NightlyHandler,
)
from mozregression.errors import LauncherError, MozRegressionError


class MockBisectorHandler(BisectorHandler):
    def _print_progress(self, new_data):
        pass


class TestBisectorHandler(unittest.TestCase):
    def setUp(self):
        self.handler = MockBisectorHandler()
        self.handler.set_build_range([{"build_url": "http://build_url_0", "repository": "my"}])

    def test_initialize(self):
        self.handler.set_build_range(
            [Mock(changeset="1", repo_url="my"), Mock(), Mock(changeset="3", repo_url="my")]
        )
        self.handler.initialize()
        self.assertEqual(self.handler.found_repo, "my")
        self.assertEqual(self.handler.good_revision, "1")
        self.assertEqual(self.handler.bad_revision, "3")

    def test_get_pushlog_url(self):
        self.handler.found_repo = "https://hg.mozilla.repo"
        self.handler.good_revision = "2"
        self.handler.bad_revision = "6"
        self.assertEqual(
            self.handler.get_pushlog_url(),
            "https://hg.mozilla.repo/pushloghtml?fromchange=2&tochange=6",
        )

    def test_get_pushlog_url_same_chsets(self):
        self.handler.found_repo = "https://hg.mozilla.repo"
        self.handler.good_revision = self.handler.bad_revision = "2"
        self.assertEqual(
            self.handler.get_pushlog_url(),
            "https://hg.mozilla.repo/pushloghtml?changeset=2",
        )

    @patch("mozregression.bisector.LOG")
    def test_print_range(self, logger):
        self.handler.found_repo = "https://hg.mozilla.repo"
        self.handler.good_revision = "2"
        self.handler.bad_revision = "6"
        log = []
        logger.info = log.append

        self.handler.print_range()
        self.assertEqual(log[0], "Last good revision: 2")
        self.assertEqual(log[1], "First bad revision: 6")
        self.assertIn(self.handler.get_pushlog_url(), log[2])

    @patch("tests.unit.test_bisector.MockBisectorHandler._print_progress")
    def test_build_good(self, _print_progress):
        self.handler.build_good(0, [{"changeset": "123"}, {"changeset": "456"}])
        _print_progress.assert_called_with([{"changeset": "123"}, {"changeset": "456"}])

    @patch("tests.unit.test_bisector.MockBisectorHandler._print_progress")
    def test_build_bad(self, _print_progress):
        # with at least two, _print_progress will be called
        self.handler.build_bad(0, [{"changeset": "123"}, {"changeset": "456"}])
        _print_progress.assert_called_with([{"changeset": "123"}, {"changeset": "456"}])


class TestNightlyHandler(unittest.TestCase):
    def setUp(self):
        self.handler = NightlyHandler()

    @patch("mozregression.bisector.BisectorHandler.initialize")
    def test_initialize(self, initialize):
        def get_associated_data(index):
            return index

        self.handler.build_range = [Mock(build_date=0), Mock(build_date=1)]
        self.handler.initialize()
        # check that members are set
        self.assertEqual(self.handler.good_date, 0)
        self.assertEqual(self.handler.bad_date, 1)

        initialize.assert_called_with(self.handler)

    @patch("mozregression.bisector.LOG")
    def test_print_progress(self, logger):
        log = []
        logger.info = log.append
        self.handler.good_date = datetime.date(2014, 11, 10)
        self.handler.bad_date = datetime.date(2014, 11, 20)

        new_data = [
            Mock(build_date=datetime.date(2014, 11, 15)),
            Mock(build_date=datetime.date(2014, 11, 20)),
        ]

        self.handler._print_progress(new_data)
        self.assertIn("from [2014-11-10, 2014-11-20] (10 days)", log[0])
        self.assertIn("to [2014-11-15, 2014-11-20] (5 days)", log[0])
        self.assertIn("2 steps left", log[0])

    @patch("mozregression.bisector.LOG")
    def test_user_exit(self, logger):
        log = []
        logger.info = log.append
        self.handler.good_date = datetime.date(2014, 11, 10)
        self.handler.bad_date = datetime.date(2014, 11, 20)
        self.handler.user_exit(0)
        self.assertEqual("Newest known good nightly: 2014-11-10", log[0])
        self.assertEqual("Oldest known bad nightly: 2014-11-20", log[1])

    @patch("mozregression.bisector.LOG")
    def test_print_range_without_repo(self, logger):
        log = []
        logger.info = log.append
        logger.error = log.append
        self.handler.good_date = datetime.date(2014, 11, 10)
        self.handler.bad_date = datetime.date(2014, 11, 20)
        self.handler.print_range()
        self.assertIn("no pushlog url available", log[0])
        self.assertEqual("Newest known good nightly: 2014-11-10", log[1])
        self.assertEqual("Oldest known bad nightly: 2014-11-20", log[2])

    @patch("mozregression.bisector.LOG")
    def test_print_range_rev_availables(self, logger):
        self.handler.found_repo = "https://hg.mozilla.repo"
        self.handler.good_revision = "2"
        self.handler.bad_revision = "6"
        self.handler.good_date = datetime.date(2015, 1, 1)
        self.handler.bad_date = datetime.date(2015, 1, 2)
        log = []
        logger.info = log.append

        self.handler.print_range()
        self.assertEqual(log[0], "Last good revision: 2 (2015-01-01)")
        self.assertEqual(log[1], "First bad revision: 6 (2015-01-02)")
        self.assertIn(self.handler.get_pushlog_url(), log[2])

    @patch("mozregression.bisector.LOG")
    def test_print_range_no_rev_availables(self, logger):
        self.handler.found_repo = "https://hg.mozilla.repo"
        self.handler.good_date = datetime.date(2014, 11, 10)
        self.handler.bad_date = datetime.date(2014, 11, 20)
        log = []
        logger.info = log.append

        self.handler.print_range()
        self.assertEqual("Newest known good nightly: 2014-11-10", log[0])
        self.assertEqual("Oldest known bad nightly: 2014-11-20", log[1])
        self.assertIn("pushloghtml?startdate=2014-11-10&enddate=2014-11-20", log[2])


class TestIntegrationHandler(unittest.TestCase):
    def setUp(self):
        self.handler = IntegrationHandler()

    @patch("mozregression.bisector.LOG")
    def test_print_progress(self, logger):
        log = []
        logger.info = log.append
        self.handler.set_build_range(
            [
                Mock(short_changeset="12"),
                Mock(short_changeset="123"),
                Mock(short_changeset="1234"),
                Mock(short_changeset="12345"),
            ]
        )
        new_data = [Mock(short_changeset="1234"), Mock(short_changeset="12345")]

        self.handler._print_progress(new_data)
        self.assertIn("from [12, 12345] (4 builds)", log[0])
        self.assertIn("to [1234, 12345] (2 builds)", log[0])
        self.assertIn("1 steps left", log[0])

    @patch("mozregression.bisector.LOG")
    def test_user_exit(self, logger):
        log = []
        logger.info = log.append
        self.handler.good_revision = "3"
        self.handler.bad_revision = "1"
        self.handler.user_exit(0)
        self.assertEqual("Newest known good integration revision: 3", log[0])
        self.assertEqual("Oldest known bad integration revision: 1", log[1])


class MyBuildData(build_range.BuildRange):
    def __init__(self, data=()):
        class FutureBuildInfo(build_range.FutureBuildInfo):
            def __init__(self, *a, **kwa):
                build_range.FutureBuildInfo.__init__(self, *a, **kwa)
                self._build_info = Mock(data=self.data)

        build_range.BuildRange.__init__(self, None, [FutureBuildInfo(None, v) for v in data])

    def __repr__(self):
        return repr([s.build_info.data for s in self._future_build_infos])

    def __eq__(self, other):
        return [s.build_info.data for s in self._future_build_infos] == [
            s.build_info.data for s in other._future_build_infos
        ]


class TestBisector(unittest.TestCase):
    def setUp(self):
        self.handler = MagicMock(find_fix=False, ensure_good_and_bad=False)
        self.test_runner = Mock()
        self.bisector = Bisector(Mock(), self.test_runner, Mock(), dl_in_background=False)
        self.bisector.download_background = False

        # shim for py2.7
        if not hasattr(self, "assertRaisesRegex"):
            self.assertRaisesRegex = self.assertRaisesRegexp

    def test__bisect_no_data(self):
        build_range = MyBuildData()
        result = self.bisector._bisect(self.handler, build_range)
        # test that handler methods where called
        self.handler.set_build_range.assert_called_with(build_range)
        self.handler.no_data.assert_called_once_with()
        # check return code
        self.assertEqual(result, Bisection.NO_DATA)

    def test__bisect_finished(self):
        build_range = MyBuildData([1])
        result = self.bisector._bisect(self.handler, build_range)
        # test that handler methods where called
        self.handler.set_build_range.assert_called_with(build_range)
        self.handler.finished.assert_called_once_with()
        # check return code
        self.assertEqual(result, Bisection.FINISHED)

    def do__bisect(self, build_range, verdicts):
        iter_verdict = iter(verdicts)

        def evaluate(build_info, allow_back=False):
            verdict = next(iter_verdict)
            if isinstance(verdict, Exception):
                raise verdict
            return verdict

        self.test_runner.evaluate = Mock(side_effect=evaluate)
        result = self.bisector._bisect(self.handler, build_range)
        return {
            "result": result,
        }

    def test_ensure_good_bad_invalid(self):
        self.handler.ensure_good_and_bad = True
        with self.assertRaisesRegex(MozRegressionError, "expected to be good"):
            self.do__bisect(MyBuildData([1, 2, 3, 4, 5]), ["b"])

        with self.assertRaisesRegex(MozRegressionError, "expected to be bad"):
            self.do__bisect(MyBuildData([1, 2, 3, 4, 5]), ["g", "g"])

    def test_ensure_good_bad(self):
        self.handler.ensure_good_and_bad = True
        data = MyBuildData([1, 2, 3, 4, 5])
        self.do__bisect(data, ["s", "r", "g", "b", "e"])
        self.test_runner.evaluate.assert_has_calls(
            [
                call(data[0]),  # tested good (then skip)
                call(data[0]),  # tested good (then retry)
                call(data[0]),  # tested good
                call(data[-1]),  # tested bad
            ]
        )
        self.assertEqual(self.bisector.download_manager.download_in_background.call_count, 0)

    def test_ensure_good_bad_with_bg_dl(self):
        self.handler.ensure_good_and_bad = True
        self.bisector.dl_in_background = True
        data = MyBuildData([1, 2, 3, 4, 5])
        self.do__bisect(data, ["s", "r", "g", "e"])
        self.test_runner.evaluate.assert_has_calls(
            [
                call(data[0]),  # tested good (then skip)
                call(data[0]),  # tested good (then retry)
                call(data[0]),  # tested good
                call(data[-1]),  # tested bad
            ]
        )
        self.bisector.download_manager.download_in_background.assert_has_calls(
            [call(data[-1]), call(data[data.mid_point()])]  # bad in backgound  # and mid build
        )

    def test_ensure_good_bad_with_find_fix(self):
        self.handler.ensure_good_and_bad = True
        self.handler.find_fix = True
        data = MyBuildData([1, 2, 3, 4, 5])
        self.do__bisect(data, ["g", "e"])
        self.test_runner.evaluate.assert_has_calls(
            [call(data[-1]), call(data[0])]  # tested good (then skip)  # tested bad
        )

    def test__bisect_case1(self):
        test_result = self.do__bisect(MyBuildData([1, 2, 3, 4, 5]), ["g", "b"])
        # check that set_build_range was called
        self.handler.set_build_range.assert_has_calls(
            [
                # first call
                call(MyBuildData([1, 2, 3, 4, 5])),
                # we answered good
                call(MyBuildData([3, 4, 5])),
                # we answered bad
                call(MyBuildData([3, 4])),
            ]
        )
        # ensure that we called the handler's methods
        self.handler.initialize.assert_called_with()
        self.handler.build_good.assert_called_with(2, MyBuildData([3, 4, 5]))
        self.handler.build_bad.assert_called_with(1, MyBuildData([3, 4]))
        self.assertTrue(self.handler.build_range.ensure_limits_called)
        # bisection is finished
        self.assertEqual(test_result["result"], Bisection.FINISHED)

    def test__bisect_with_launcher_exception(self):
        test_result = self.do__bisect(MyBuildData([1, 2, 3, 4, 5]), ["g", LauncherError("err")])
        # check that set_build_range was called
        self.handler.set_build_range.assert_has_calls(
            [
                # first call
                call(MyBuildData([1, 2, 3, 4, 5])),
                # we answered good
                call(MyBuildData([3, 4, 5])),
                # launcher exception, equivalent to a skip
                call(MyBuildData([3, 5])),
            ]
        )
        # ensure that we called the handler's methods
        self.handler.initialize.assert_called_with()
        self.handler.build_good.assert_called_with(2, MyBuildData([3, 4, 5]))
        self.handler.build_skip.assert_called_with(1)
        self.assertTrue(self.handler.build_range.ensure_limits_called)
        # bisection is finished
        self.assertEqual(test_result["result"], Bisection.FINISHED)

    def test__bisect_case1_hunt_fix(self):
        self.handler.find_fix = True
        test_result = self.do__bisect(MyBuildData([1, 2, 3, 4, 5]), ["g", "b"])
        # check that set_build_range was called
        self.handler.set_build_range.assert_has_calls(
            [
                # first call
                call(MyBuildData([1, 2, 3, 4, 5])),
                # we answered good
                call(MyBuildData([1, 2, 3])),
                # we answered bad
                call(MyBuildData([2, 3])),
            ]
        )
        # ensure that we called the handler's methods
        self.assertEqual(self.handler.initialize.mock_calls, [call()] * 3)
        self.handler.build_good.assert_called_once_with(2, MyBuildData([1, 2, 3]))
        self.handler.build_bad.assert_called_once_with(1, MyBuildData([2, 3]))
        # bisection is finished
        self.assertEqual(test_result["result"], Bisection.FINISHED)

    def test__bisect_case2(self):
        test_result = self.do__bisect(MyBuildData([1, 2, 3]), ["r", "s"])
        # check that set_build_range was called
        self.handler.set_build_range.assert_has_calls(
            [
                # first call
                call(MyBuildData([1, 2, 3])),
                # we asked for a retry
                call(MyBuildData([1, 2, 3])),
                # we skipped one
                call(MyBuildData([1, 3])),
            ]
        )
        # ensure that we called the handler's methods
        self.handler.initialize.assert_called_with()
        self.handler.build_retry.assert_called_with(1)
        self.handler.build_skip.assert_called_with(1)
        self.assertTrue(self.handler.build_range.ensure_limits_called)
        # bisection is finished
        self.assertEqual(test_result["result"], Bisection.FINISHED)

    def test__bisect_with_back(self):
        test_result = self.do__bisect(MyBuildData([1, 2, 3, 4, 5]), ["g", "back", "b", "g"])
        # check that set_build_range was called
        self.handler.set_build_range.assert_has_calls(
            [
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
            ]
        )
        # bisection is finished
        self.assertEqual(test_result["result"], Bisection.FINISHED)

    def test__bisect_user_exit(self):
        test_result = self.do__bisect(MyBuildData(list(range(20))), ["e"])
        # check that set_build_range was called
        self.handler.set_build_range.assert_has_calls([call(MyBuildData(list(range(20))))])
        # ensure that we called the handler's method
        self.handler.initialize.assert_called_once_with()
        self.handler.user_exit.assert_called_with(10)
        # user exit
        self.assertEqual(test_result["result"], Bisection.USER_EXIT)

    def test__bisect_with_background_download(self):
        self.bisector.dl_in_background = True
        test_result = self.do__bisect(MyBuildData([1, 2, 3, 4, 5]), ["g", "b"])
        # check that set_build_range was called
        self.handler.set_build_range.assert_has_calls(
            [
                call(MyBuildData([1, 2, 3, 4, 5])),  # first call
                call(MyBuildData([3, 4, 5])),  # we answered good
                call(MyBuildData([3, 4])),  # we answered bad
            ]
        )
        # ensure that we called the handler's methods
        self.handler.initialize.assert_called_with()
        self.handler.build_good.assert_called_with(2, MyBuildData([3, 4, 5]))
        self.handler.build_bad.assert_called_with(1, MyBuildData([3, 4]))
        self.assertTrue(self.handler.build_range.ensure_limits_called)
        # bisection is finished
        self.assertEqual(test_result["result"], Bisection.FINISHED)

    @patch("mozregression.bisector.Bisector._bisect")
    def test_bisect(self, _bisect):
        _bisect.return_value = 1
        build_range = Mock()
        create_range = Mock(return_value=build_range)
        self.handler.create_range = create_range
        result = self.bisector.bisect(self.handler, "g", "b", s=1)
        create_range.assert_called_with(self.bisector.fetch_config, "g", "b", s=1)
        self.assertFalse(build_range.reverse.called)
        _bisect.assert_called_with(self.handler, build_range)
        self.assertEqual(result, 1)

    @patch("mozregression.bisector.Bisector._bisect")
    def test_bisect_reverse(self, _bisect):
        build_range = Mock()
        create_range = Mock(return_value=build_range)
        self.handler.create_range = create_range
        self.handler.find_fix = True
        self.bisector.bisect(self.handler, "g", "b", s=1)
        create_range.assert_called_with(self.bisector.fetch_config, "b", "g", s=1)
        _bisect.assert_called_with(self.handler, build_range)


if __name__ == "__main__":
    unittest.main()
