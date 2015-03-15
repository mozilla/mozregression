# Import PySide classes
import sys
from PySide.QtGui import QApplication, QMainWindow
from PySide.QtCore import Slot

from mozlog.structured import set_default_logger
from mozlog.structured.structuredlog import StructuredLogger

from mozregui.ui.mainwindow import Ui_MainWindow
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
        self.ui.bisect_options.ui.start_bisection.clicked.connect(
            self.start_bisection)

    @Slot()
    def start_bisection(self):
        fetch_config = self.ui.bisect_options.fetch_config()
        options = self.ui.bisect_options.bisect_options()
        self.bisect_runner.bisect(fetch_config, options)


if __name__ == '__main__':
    set_default_logger(StructuredLogger('mozregression-gui'))
    # Create a Qt application
    app = QApplication(sys.argv)
    # Create the main window and show it
    win = MainWindow()
    app.aboutToQuit.connect(win.bisect_runner.stop)
    win.show()
    # Enter Qt application main loop
    sys.exit(app.exec_())
