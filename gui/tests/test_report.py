import unittest
from PyQt4.QtTest import QTest
from PyQt4.QtCore import Qt
from mock import Mock

from mozregui.report import ReportView


class TestReport(unittest.TestCase):
    def setUp(self):
        self.view = ReportView()

    def test_basic(self):
        # TODO: rewrite all this.

        slot = Mock()
        self.view.step_report_changed.connect(slot)
        # show the widget
        self.view.show()
        QTest.qWaitForWindowShown(self.view)
        # start the bisection
        self.view.model().started()
        self.view.model().step_started(Mock())
        # a row is inserted
        index = self.view.model().index(0, 0)
        self.assertTrue(index.isValid())

        # simulate a build found
        build_infos = {"build_type": 'nightly', 'build_date': 'date'}
        bisection = Mock()
        bisection.handler.get_range.return_value = (1, 2)
        self.view.model().step_build_found(bisection, build_infos)
        # now we have two rows
        self.assertEquals(self.view.model().rowCount(), 2)
        # data is updated
        index2 = self.view.model().index(1, 0)
        self.assertIn('[1 - 2]', self.view.model().data(index))
        self.assertIn('nightly', self.view.model().data(index2))

        # simulate a build evaluation
        self.view.model().step_finished(None, 'g')
        # still two rows
        self.assertEquals(self.view.model().rowCount(), 2)
        # data is updated
        self.assertIn('g', self.view.model().data(index2))

        # let's click on the index
        self.view.scrollTo(index)
        rect = self.view.visualRect(index)
        QTest.mouseClick(self.view.viewport(), Qt.LeftButton,
                         pos=rect.center())
        # signal has been emitted
        self.assertEquals(slot.call_count, 1)

        # let's simulate another bisection step
        bisection = Mock()
        bisection.handler.get_pushlog_url.return_value = "http://pl"
        self.view.model().step_started(bisection)
        self.assertEquals(self.view.model().rowCount(), 3)
        # then say that it's the end
        self.view.model().finished(bisection, None)
        # this last row is removed now
        self.assertEquals(self.view.model().rowCount(), 2)
