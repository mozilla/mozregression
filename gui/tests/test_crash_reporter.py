import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton

from mozregui.crash_reporter import CrashDialog, CrashReporter


class CrashDlgTest(CrashDialog):
    INSTANCE = None

    # do not block
    def exec(self):
        self.show()
        CrashDlgTest.INSTANCE = self


@pytest.fixture
def crash_reporter():
    reporter = CrashReporter(QApplication.instance())
    reporter.DIALOG_CLASS = CrashDlgTest
    reporter.install()
    yield reporter
    reporter.uninstall()


class CrashingButton(QPushButton):
    def __init__(self):
        QPushButton.__init__(self)
        self.clicked.connect(self.crash, Qt.QueuedConnection)

    def crash(self):
        raise Exception("oh, no!")


@pytest.mark.qt_no_exception_capture
def test_report_exception(crash_reporter, qtbot, mocker):
    btn = CrashingButton()
    qtbot.addWidget(btn)

    btn.show()

    with qtbot.waitExposed(btn):
        pass

    with qtbot.waitSignal(crash_reporter.got_exception):
        qtbot.mouseClick(btn, Qt.LeftButton)

    while not CrashDlgTest.INSTANCE:
        crash_reporter.app.processEvents()
    dlg = CrashDlgTest.INSTANCE
    with qtbot.waitExposed(dlg):
        pass
    text = str(dlg.ui.information.toPlainText())
    assert "oh, no!" in text
