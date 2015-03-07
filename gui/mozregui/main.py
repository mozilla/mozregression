# Import PySide classes
import sys
from PySide.QtGui import QApplication, QMainWindow
from PySide.QtCore import Slot

from mozlog.structured import set_default_logger
from mozlog.structured.structuredlog import StructuredLogger

from mozregui.ui.mainwindow import Ui_MainWindow
from mozregui.wizard import BisectionWizard
from mozregui.bisection import BisectRunner


class MainWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.bisect_runner = BisectRunner(self)

        self.bisect_runner.bisector_created.connect(
            self.ui.report_view.model().attach_bisector)
        self.ui.report_view.step_report_selected.connect(
            self.ui.build_info_edit.update_content)

    @Slot()
    def start_bisection_wizard(self):
        wizard = BisectionWizard(self)
        if wizard.exec_() == wizard.Accepted:
            self.bisect_runner.bisect(wizard.field_options())


if __name__ == '__main__':
    set_default_logger(StructuredLogger('mozregression-gui'))
    # Create a Qt application
    app = QApplication(sys.argv)
    # Create the main window and show it
    win = MainWindow()
    app.aboutToQuit.connect(win.bisect_runner.stop)
    win.show()
    win.start_bisection_wizard()
    # Enter Qt application main loop
    sys.exit(app.exec_())
