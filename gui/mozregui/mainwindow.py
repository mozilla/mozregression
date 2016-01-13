
import mozregression
import mozregui
import mozfile

from tempfile import mkdtemp
from PyQt4.QtGui import QMainWindow, QMessageBox
from PyQt4.QtCore import pyqtSlot as Slot, QSettings

from mozregui.ui.mainwindow import Ui_MainWindow
from mozregui.wizard import BisectionWizard, SingleRunWizard
from mozregui.bisection import BisectRunner
from mozregui.single_runner import SingleBuildRunner
from mozregui.global_prefs import change_prefs_dialog
from mozregui.report_delegate import ReportItemDelegate


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
    INSTANCE = None

    def __init__(self):
        QMainWindow.__init__(self)
        MainWindow.INSTANCE = self
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

        self.ui.report_view.model().need_evaluate_editor.connect(
            self.bisect_runner.open_evaluate_editor)

        self.ui.report_view.step_report_changed.connect(
            self.ui.build_info_browser.update_content)
        self.report_delegate = ReportItemDelegate()
        self.report_delegate.got_verdict.connect(
            self.bisect_runner.set_verdict
        )
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

    def _start_runner(self, wizard_class, runner):
        wizard = wizard_class(self)
        if wizard.exec_() == wizard.Accepted:
            self.current_runner = runner
            # clear the report model
            self.ui.report_view.model().clear()
            # clear the build info main panel
            self.ui.build_info_browser.clear()

            runner.start(*wizard.options())

    @Slot()
    def start_bisection_wizard(self):
        self._start_runner(BisectionWizard, self.bisect_runner)

    @Slot()
    def stop_bisection(self):
        # stop the bisection or the single runner without blocking
        self.ui.report_view.model().attach_bisector(None)
        self.current_runner.stop(False)

    @Slot()
    def single_run(self):
        self._start_runner(SingleRunWizard, self.single_runner)

    @Slot()
    def show_about(self):
        QMessageBox.about(self, "About", ABOUT_TEXT)

    @Slot()
    def edit_global_prefs(self):
        change_prefs_dialog(self)
