# first thing, patch requests lib if required
from mozregui import patch_requests
patch_requests.patch()

# Import PyQt4 classes
import sys
import mozregression
import mozregui
import mozfile
from tempfile import mkdtemp
from PyQt4.QtGui import QApplication, QMainWindow, QMessageBox
from PyQt4.QtCore import pyqtSlot as Slot, QSettings

from mozlog.structuredlog import set_default_logger, StructuredLogger

from mozregui.ui.mainwindow import Ui_MainWindow
from mozregui.wizard import BisectionWizard, SingleRunWizard
from mozregui.bisection import BisectRunner
from mozregui.single_runner import SingleBuildRunner
from mozregui.global_prefs import change_prefs_dialog
from mozregui.log_report import LogModel
from mozregui.report_delegate import ReportItemDelegate
from mozregui.check_release import CheckRelease
from mozregui.crash_reporter import CrashReporter


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

        # Init MenuViews
        self.ui.actionLogView.setChecked(self.ui.logDockWidget.isVisible())
        self.ui.actionToolBar.setChecked(self.ui.toolBar.isVisible())

        self.bisect_runner = BisectRunner(self)
        self.single_runner = SingleBuildRunner(self)
        self.current_runner = None

        self.bisect_runner.worker_created.connect(
            self.ui.report_view.model().attach_bisector)
        self.single_runner.worker_created.connect(
            self.ui.report_view.model().attach_single_runner)

        self.ui.report_view.step_report_changed.connect(
            self.ui.build_info_browser.update_content)
        self.report_delegate = ReportItemDelegate()
        self.ui.report_view.setItemDelegateForColumn(0, self.report_delegate)

        for runner in (self.bisect_runner, self.single_runner):
            runner.running_state_changed.connect(
                self.ui.actionStart_a_new_bisection.setDisabled)
            runner.running_state_changed.connect(
                self.ui.actionStop_the_bisection.setEnabled)
            runner.running_state_changed.connect(
                self.ui.actionRun_a_single_build.setDisabled)

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
            self.current_runner = self.bisect_runner
            self.ui.report_view.model().clear()
            self.bisect_runner.start(*wizard.options())

    @Slot()
    def stop_bisection(self):
        # stop the bisection or the single runner without blocking
        model = self.ui.report_view.model()
        model.attach_bisector(None)
        self.current_runner.stop(False)
        # clear the report model
        model.clear()
        # clear the build info main panel
        self.ui.build_info_browser.clear()

    @Slot()
    def single_run(self):
        wizard = SingleRunWizard(self)
        if wizard.exec_() == wizard.Accepted:
            self.current_runner = self.single_runner
            self.single_runner.start(*wizard.options())

    @Slot()
    def show_about(self):
        QMessageBox.about(self, "About", ABOUT_TEXT)

    @Slot()
    def edit_global_prefs(self):
        change_prefs_dialog(self)


def main():
    logger = StructuredLogger('mozregression-gui')
    set_default_logger(logger)
    # Create a Qt application
    log_model = LogModel()
    logger.add_handler(log_model)
    argv = [sys.argv[0].replace("main.py", "mozregression")] + sys.argv[1:]
    app = QApplication(argv)
    crash_reporter = CrashReporter(app)
    crash_reporter.install()
    app.setOrganizationName('mozilla')
    app.setOrganizationDomain('mozilla.org')
    app.setApplicationName('mozregression-gui')
    # Create the main window and show it
    win = MainWindow()
    app.aboutToQuit.connect(win.bisect_runner.stop)
    app.aboutToQuit.connect(win.single_runner.stop)
    app.aboutToQuit.connect(win.clear)
    release_checker = CheckRelease(win)
    release_checker.check()
    log_model.log.connect(win.ui.log_view.on_log_received)
    win.show()
    # Enter Qt application main loop
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
