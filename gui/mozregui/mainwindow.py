from tempfile import mkdtemp

import mozfile
from PySide2.QtCore import QSettings, Slot
from PySide2.QtWidgets import QMainWindow, QMessageBox

from mozregression import __version__ as mozregression_version
from mozregression.telemetry import initialize_telemetry
from mozregui.bisection import BisectRunner
from mozregui.global_prefs import change_prefs_dialog, get_prefs
from mozregui.report_delegate import ReportItemDelegate
from mozregui.single_runner import SingleBuildRunner
from mozregui.ui.mainwindow import Ui_MainWindow
from mozregui.wizard import BisectionWizard, SingleRunWizard

ABOUT_TEXT = """\
<p><strong>mozregression-gui</strong> is a desktop interface for
<strong>mozregression</strong>, a regression range finder for Mozilla
nightly and integration builds.</p>
<p><a href="http://mozilla.github.io/mozregression/">\
http://mozilla.github.io/mozregression/</a></p>
<p><b>Using mozregression version: %s</b></p>
<p>mozregression logo by <a href="https://mozillians.org/en-US/u/victoria/">Victoria Wang</a></p>
<p>All application icons are made by <a href="http://www.freepik.com"
                              title="Freepik">Freepik</a>
from <a href="http://www.flaticon.com" title="Flaticon">www.flaticon.com</a>
and licensed under <a href="http://creativecommons.org/licenses/by/3.0/"
                      title="Creative Commons BY 3.0">CC BY 3.0</a></p>
""" % (
    mozregression_version
)


class MainWindow(QMainWindow):
    INSTANCE = None

    def __init__(self):
        QMainWindow.__init__(self)
        MainWindow.INSTANCE = self
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.bisect_runner = BisectRunner(self)
        self.single_runner = SingleBuildRunner(self)
        self.current_runner = None

        self.bisect_runner.worker_created.connect(self.ui.report_view.model().attach_bisector)
        self.single_runner.worker_created.connect(self.ui.report_view.model().attach_single_runner)

        self.ui.report_view.model().need_evaluate_editor.connect(
            self.bisect_runner.open_evaluate_editor
        )

        self.ui.report_view.step_report_changed.connect(self.ui.build_info_browser.update_content)
        self.report_delegate = ReportItemDelegate()
        self.report_delegate.got_verdict.connect(self.bisect_runner.set_verdict)
        self.ui.report_view.setItemDelegateForColumn(0, self.report_delegate)

        for runner in (self.bisect_runner, self.single_runner):
            runner.running_state_changed.connect(self.ui.actionStart_a_new_bisection.setDisabled)
            runner.running_state_changed.connect(self.ui.actionStop_the_bisection.setEnabled)
            runner.running_state_changed.connect(self.ui.actionRun_a_single_build.setDisabled)

        self.persist = mkdtemp()

        self.read_settings()

        # get weird behaviour if we enable multiprocessing on pyinstaller builds of the GUI
        initialize_telemetry(get_prefs()["enable_telemetry"], allow_multiprocessing=False)

        # Make sure the toolbar and logviews are visible (in case
        # the user manually turned them off in a previous release
        # where this was possible)
        self.ui.toolBar.setVisible(True)
        self.ui.log_view.setVisible(True)
        self.ui.logDockWidget.setVisible(True)

    @Slot()
    def clear(self):
        mozfile.remove(self.persist)

    def read_settings(self):
        settings = QSettings()
        self.restoreGeometry(settings.value("mainWin/geometry"))
        self.restoreState(settings.value("mainWin/windowState"))

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
