# Import PyQt4 classes
import sys
import mozregression
import mozregui
import mozfile
from tempfile import mkdtemp
from datetime import datetime
from PyQt4.QtGui import QApplication, QMainWindow, QMessageBox, QTextCursor
from PyQt4.QtCore import pyqtSlot as Slot, QSettings, QObject, \
    pyqtSignal as Signal

from mozlog.structured import set_default_logger
from mozlog.structured.structuredlog import StructuredLogger

from mozregui.ui.mainwindow import Ui_MainWindow
from mozregui.wizard import BisectionWizard
from mozregui.bisection import BisectRunner
from mozregui.global_prefs import change_prefs_dialog


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
        self.bisect_runner.running_state_changed.connect(
            self.ui.actionStart_a_new_bisection.setDisabled)
        self.bisect_runner.running_state_changed.connect(
            self.ui.actionStop_the_bisection.setEnabled)

        self.persist = mkdtemp()

        self.read_settings()

    @Slot()
    def clear(self):
        mozfile.remove(self.persist)

    def read_settings(self):
        settings = QSettings()
        self.restoreGeometry(settings.value("mainWin/geometry").toByteArray())
        self.restoreState(settings.value("mainWin/windowState").toByteArray())

    def closeEvent(self, evt):
        settings = QSettings()
        settings.setValue("mainWin/geometry", self.saveGeometry())
        settings.setValue("mainWin/windowState", self.saveState())
        QMainWindow.closeEvent(self, evt)

    @Slot()
    def start_bisection_wizard(self):
        wizard = BisectionWizard(self)
        if wizard.exec_() == wizard.Accepted:
            self.ui.report_view.model().clear()
            self.bisect_runner.bisect(*wizard.options())

    @Slot()
    def stop_bisection(self):
        # stop the bisection without blocking
        self.bisect_runner.stop(False)
        # clear the report model
        model = self.ui.report_view.model()
        model.attach_bisector(None)
        model.clear()
        # clear the build info main panel
        self.ui.build_info_browser.clear()

    @Slot()
    def show_about(self):
        QMessageBox.about(self, "About", ABOUT_TEXT)

    @Slot()
    def edit_global_prefs(self):
        change_prefs_dialog(self)

    @Slot(dict)
    def on_log_received(self, data):
        time_info = datetime.fromtimestamp((data['time']/1000)).isoformat()
        log_message = '%s: %s : %s' % (
            time_info, data['level'], data['message'])
        self.ui.log_information_view.appendPlainText(log_message)
        counter = self.ui.log_information_view.blockCount()

        if(counter > 1000):
            document = self.ui.log_information_view.document()
            cursor = QTextCursor(document.findBlockByLineNumber(0))
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.deleteChar()
            cursor.deleteChar()


class LogModel(QObject):
    log = Signal(dict)

    def __call__(self, data):
        self.log.emit(data)


def main():
    set_default_logger(StructuredLogger('mozregression-gui'))
    # Create a Qt application
    log_model = LogModel()
    StructuredLogger('mozregression-gui').add_handler(log_model)
    argv = [sys.argv[0].replace("main.py", "mozregression")] + sys.argv[1:]
    app = QApplication(argv)
    app.setOrganizationName('mozilla')
    app.setOrganizationDomain('mozilla.org')
    app.setApplicationName('mozregression-gui')
    # Create the main window and show it
    win = MainWindow()
    app.aboutToQuit.connect(win.bisect_runner.stop)
    app.aboutToQuit.connect(win.clear)
    log_model.log.connect(win.on_log_received)
    win.show()
    win.start_bisection_wizard()
    # Enter Qt application main loop
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
