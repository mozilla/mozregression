# Import PySide classes
import sys
from PySide.QtGui import QApplication, QMainWindow
from PySide.QtCore import Slot

from mozlog.structured import set_default_logger
from mozlog.structured.structuredlog import StructuredLogger

from mozregui.ui.mainwindow import Ui_MainWindow
from mozregui.wizard import BisectionWizard
from mozregui.bisection import BisectRunner
from mozregui.report import ReportModel


class MainWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.bisect_runner = BisectRunner(self)

        self.report_model = ReportModel()
        self.ui.report_view.setModel(self.report_model)

        self.bisect_runner.bisector_created.connect(
            self.report_model.attach_bisector)

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
