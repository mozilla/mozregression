import unittest
from PySide.QtTest import QTest
from PySide.QtCore import Qt
from mock import Mock

from mozregui.report import ReportView


class TestReport(unittest.TestCase):
    def setUp(self):
        self.view = ReportView()

    def test_basic(self):
        slot = Mock()
        self.view.step_report_selected.connect(slot)
        # show the widget
        self.view.show()
        QTest.qWaitForWindowShown(self.view)
        # insert a row
        self.view.model().started()
        self.view.model().step_started(None, 1)
        # a row is inserted
        index = self.view.model().index(0, 0)
        self.assertTrue(index.isValid())

        # simulate a build found
        build_infos = {"build_type": 'nightly', 'build_date': 'date'}
        self.view.model().step_build_found(None, 1, build_infos)
        # still one row
        self.assertEquals(self.view.model().rowCount(), 1)
        # data is updated
        self.assertIn('nightly', self.view.model().data(index))

        # simulate a build evaluation
        self.view.model().step_finished(None, 1, 'g')
        # still one row
        self.assertEquals(self.view.model().rowCount(), 1)
        # data is updated
        self.assertIn('g', self.view.model().data(index))

        # let's click on the index
        self.view.scrollTo(index)
        rect = self.view.visualRect(index)
        QTest.mouseClick(self.view.viewport(), Qt.LeftButton,
                         pos=rect.center())
        # signal has been emitted
        self.assertEquals(slot.call_count, 1)

        # let's simulate another bisection step
        self.view.model().step_started(None, 2)
        self.assertEquals(self.view.model().rowCount(), 2)
        # then say that it's the end
        self.view.model().finished(None, None)
        # this last row is removed now
        self.assertEquals(self.view.model().rowCount(), 1)
