# Import PyQt4 classes
import sys
import mozregression
import mozregui
from PyQt4.QtGui import QApplication, QMainWindow, QMessageBox
from PyQt4.QtCore import pyqtSlot as Slot

from mozlog.structured import set_default_logger
from mozlog.structured.structuredlog import StructuredLogger

from mozregui.ui.mainwindow import Ui_MainWindow
from mozregui.wizard import BisectionWizard
from mozregui.bisection import BisectRunner


ABOUT_TEXT = """\
<p><strong>mozregression-gui</strong> is a desktop interface for
<strong>mozregression</strong>, a regression range finder for Mozilla
nightly and inbound builds.</p>
<br>
<a href="http://mozilla.github.io/mozregression/">\
http://mozilla.github.io/mozregression/</a>
<br>
<ul>
<li>Version: %s</li>
<li>Using mozregression version: %s</li>
</ul>
<div>All icons are made by <a href="http://www.freepik.com"
                              title="Freepik">Freepik</a>
from <a href="http://www.flaticon.com" title="Flaticon">www.flaticon.com</a>
and licensed under <a href="http://creativecommons.org/licenses/by/3.0/"
                      title="Creative Commons BY 3.0">CC BY 3.0</a></div>
""" % (mozregui.__version__, mozregression.__version__)


class MainWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.bisect_runner = BisectRunner(self)

        self.bisect_runner.bisector_created.connect(
            self.ui.report_view.model().attach_bisector)
        self.ui.report_view.step_report_changed.connect(
            self.ui.build_info_browser.update_content)

    @Slot()
    def start_bisection_wizard(self):
        wizard = BisectionWizard(self)
        if wizard.exec_() == wizard.Accepted:
            self.ui.report_view.model().clear()
            self.bisect_runner.bisect(*wizard.options())

    @Slot()
    def show_about(self):
        QMessageBox.about(self, "About", ABOUT_TEXT)


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
