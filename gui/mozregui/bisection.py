import sys
from PyQt4.QtCore import QObject, pyqtSignal as Signal, pyqtSlot as Slot, \
    QThread, QTimer
from PyQt4.QtGui import QMessageBox, QDialog, QRadioButton

from mozregression.bisector import Bisector, Bisection, NightlyHandler, \
    InboundHandler
from mozregression.download_manager import BuildDownloadManager
from mozregression.test_runner import TestRunner
from mozregression.errors import MozRegressionError, LauncherError
from mozregression.network import get_http_session

from mozregui.ui.verdict import Ui_Verdict
from mozregui.global_prefs import get_prefs, apply_prefs

Bisection.EXCEPTION = -1  # new possible value of bisection end


class GuiBuildDownloadManager(QObject, BuildDownloadManager):
    download_progress = Signal(object, int, int)
    download_started = Signal(object)
    download_finished = Signal(object, str)

    def __init__(self, destdir, **kwargs):
        QObject.__init__(self)
        BuildDownloadManager.__init__(self, destdir,
                                      session=get_http_session(),
                                      **kwargs)

    def _download_started(self, task):
        self.download_started.emit(task)
        BuildDownloadManager._download_started(self, task)

    def _download_finished(self, task):
        try:
            self.download_finished.emit(task, task.get_dest())
        except RuntimeError:
            # in some cases, closing the application may destroy the
            # underlying c++ QObject, causing this signal to fail.
            # Skip this silently.
            pass
        BuildDownloadManager._download_finished(self, task)

    def focus_download(self, build_info):
        build_url, fname = self._extract_download_info(build_info)
        dest = self.get_dest(fname)
        build_info.build_file = dest
        # first, stop all downloads in background (except the one for this
        # build if any)
        self.cancel(cancel_if=lambda dl: dest != dl.get_dest())

        dl = self.download(build_url, fname)
        if dl:
            dl.set_progress(self.download_progress.emit)
        else:
            # file already downloaded.
            # emit the finished signal so bisection goes on
            self.download_finished.emit(None, dest)


class GuiTestRunner(QObject, TestRunner):
    evaluate_started = Signal(str)
    evaluate_finished = Signal()

    def __init__(self):
        QObject.__init__(self)
        TestRunner.__init__(self)
        self.verdict = None
        self.launcher = None
        self.launcher_kwargs = {}

    def evaluate(self, build_info, allow_back=False):
        try:
            self.launcher = self.create_launcher(build_info)
            self.launcher.start(**self.launcher_kwargs)
            build_info.update_from_app_info(self.launcher.get_app_info())
        except LauncherError, exc:
            self.evaluate_started.emit(str(exc))
        else:
            self.evaluate_started.emit('')

    def finish(self, verdict):
        if self.launcher:
            try:
                self.launcher.stop()
            except LauncherError:
                pass  # silently pass stop process error
            self.launcher.cleanup()
        self.verdict = verdict
        self.evaluate_finished.emit()


class GuiBisector(QObject, Bisector):
    started = Signal()
    finished = Signal(object, int)
    step_started = Signal(object)
    step_build_found = Signal(object, object)
    step_testing = Signal(object, object)
    step_finished = Signal(object, str)

    def __init__(self, fetch_config, download_dir):
        QObject.__init__(self)
        Bisector.__init__(self, fetch_config, GuiTestRunner(),
                          GuiBuildDownloadManager(download_dir))
        self.bisection = None
        self.mid = None
        self.build_infos = None
        self._bisect_args = None
        self.error = None

        self.download_manager.download_finished.connect(
            self._build_dl_finished)
        self.test_runner.evaluate_finished.connect(self._evaluate_finished)

    def _finish_on_exception(self, bisection):
        self.error = sys.exc_info()
        self.finished.emit(bisection, Bisection.EXCEPTION)

    @Slot()
    def bisect(self):
        # this is a slot so it will be called in the thread
        self.started.emit()
        try:
            Bisector.bisect(self, *self._bisect_args)
        except MozRegressionError:
            self._finish_on_exception(None)

    @Slot()
    def nightlies_to_inbound(self):
        """
        Call this when going from nightlies to inbound.
        """
        assert self.bisection
        self.started.emit()
        try:
            # first we need to find the changesets
            first, last = self.bisection.handler.find_inbound_changesets()
            # create the inbound handler, and go with that
            handler = InboundHandler(find_fix=self.bisection.handler.find_fix)
            Bisector.bisect(self, handler, first, last)
        except MozRegressionError:
            self._finish_on_exception(None)

    def _bisect(self, handler, build_range):
        self.bisection = Bisection(handler, build_range,
                                   self.download_manager,
                                   self.test_runner,
                                   self.fetch_config,
                                   dl_in_background=False)
        self._bisect_next()

    @Slot()
    def _bisect_next(self):
        # this is executed in the working thread
        self.step_started.emit(self.bisection)
        try:
            self.mid = mid = self.bisection.search_mid_point()
        except MozRegressionError:
            self._finish_on_exception(self.bisection)
            return
        result = self.bisection.init_handler(mid)
        if result != Bisection.RUNNING:
            self.finished.emit(self.bisection, result)
        else:
            self.build_infos = self.bisection.handler.build_range[mid]
            self.download_manager.focus_download(self.build_infos)
            self.step_build_found.emit(self.bisection, self.build_infos)

    @Slot()
    def _evaluate(self):
        # this is called in the working thread, so installation does not
        # block the ui.
        self.bisection.evaluate(self.build_infos)

    @Slot(object, str)
    def _build_dl_finished(self, dl, dest):
        # here we are not in the working thread, since the connection was
        # done in the constructor
        if not dest == self.build_infos.build_file:
            return
        if dl is not None and (dl.is_canceled() or dl.error()):
            # todo handle this
            return
        self.step_testing.emit(self.bisection, self.build_infos)
        # call this in the thread
        QTimer.singleShot(0, self._evaluate)

    @Slot()
    def _evaluate_finished(self):
        # here we are not in the working thread, since the connection was
        # done in the constructor
        self.step_finished.emit(self.bisection, self.test_runner.verdict)
        result = self.bisection.handle_verdict(self.mid,
                                               self.test_runner.verdict)
        if result != Bisection.RUNNING:
            self.finished.emit(self.bisection, result)
        else:
            # call this in the thread
            QTimer.singleShot(0, self._bisect_next)


def get_verdict(parent=None):
    dlg = QDialog(parent)
    ui = Ui_Verdict()
    ui.setupUi(dlg)
    if dlg.exec_() != QDialog.Accepted:
        return 'e'  # exit bisection
    for radiobox in dlg.findChildren(QRadioButton):
        if radiobox.isChecked():
            return radiobox.objectName()


class BisectRunner(QObject):
    bisector_created = Signal(object)
    running_state_changed = Signal(bool)

    def __init__(self, mainwindow):
        QObject.__init__(self)
        self.mainwindow = mainwindow
        self.bisector = None
        self.thread = None
        self.pending_threads = []

    def bisect(self, fetch_config, options):
        self.stop()

        # global preferences
        global_prefs = get_prefs()
        # apply the global prefs now
        apply_prefs(global_prefs)

        download_dir = global_prefs['persist']
        if not download_dir:
            download_dir = self.mainwindow.persist

        self.bisector = GuiBisector(fetch_config,
                                    download_dir)
        # create a QThread, and move self.bisector in it. This will
        # allow to the self.bisector slots (connected after the move)
        # to be automatically called in the thread.
        self.thread = QThread()
        self.bisector.moveToThread(self.thread)
        self.bisector.test_runner.evaluate_started.connect(
            self.evaluate)
        self.bisector.finished.connect(self.bisection_finished)
        self.bisector_created.emit(self.bisector)
        if options['bisect_type'] == 'nightlies':
            handler = NightlyHandler(find_fix=options['find_fix'])
            good = options['good_date']
            bad = options['bad_date']
        else:
            handler = InboundHandler(find_fix=options['find_fix'])
            good = options['good_changeset']
            bad = options['bad_changeset']

        # options for the app launcher
        launcher_kwargs = {}
        for name in ('profile', 'preferences'):
            if name in options:
                value = options[name]
                if value:
                    launcher_kwargs[name] = value

        # add add-ons paths to the app launcher
        launcher_kwargs['addons'] = options['addons']
        self.bisector.test_runner.launcher_kwargs = launcher_kwargs

        self.thread.start()
        self.bisector._bisect_args = (handler, good, bad)
        # this will be called in the worker thread.
        QTimer.singleShot(0, self.bisector.bisect)

        self.running_state_changed.emit(True)

    @Slot()
    def stop(self, wait=True):
        if self.bisector:
            self.bisector.finished.disconnect(self.bisection_finished)
            self.bisector.download_manager.cancel()
            self.bisector = None
        if self.thread:
            self.thread.quit()
            if wait:
                # wait for thread(s) completion - this is the case when
                # user close the application
                self.thread.wait()
                for thread in self.pending_threads:
                    thread.wait()
            else:
                # do not block, just keep track of the thread - we got here
                # when user cancel the bisection with the button.
                self.pending_threads.append(self.thread)
                self.thread.finished.connect(self._remove_pending_thread)
            self.thread = None
        self.running_state_changed.emit(False)

    @Slot()
    def _remove_pending_thread(self):
        for thread in self.pending_threads[:]:
            if thread.isFinished():
                self.pending_threads.remove(thread)

    @Slot(str)
    def evaluate(self, err_message):
        if not err_message:
            verdict = get_verdict(self.mainwindow)
        else:
            QMessageBox.warning(
                self.mainwindow,
                "Launcher Error",
                ("An error occured while starting the process, so the build"
                 " will be skipped. Error message:<br><strong>%s</strong>"
                 % err_message)
            )
            verdict = 's'
        self.bisector.test_runner.finish(verdict)

    @Slot(object, int)
    def bisection_finished(self, bisection, resultcode):
        if resultcode == Bisection.USER_EXIT:
            msg = "Bisection stopped."
            dialog = QMessageBox.information
        elif resultcode == Bisection.NO_DATA:
            msg = "Unable to find enough data to bisect."
            dialog = QMessageBox.warning
        elif resultcode == Bisection.EXCEPTION:
            msg = "Error: %s" % self.bisector.error[1]
            dialog = QMessageBox.critical
        else:
            if bisection.fetch_config.can_go_inbound() and \
                    isinstance(bisection.handler, NightlyHandler):
                # we can go on inbound, let's ask the user
                if QMessageBox.question(
                    self.mainwindow,
                    "End of the bisection",
                    "Nightly bisection is done, but you can continue the"
                    " bisection on inbound builds. Continue with inbounds ?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                ) == QMessageBox.Yes:
                    # let's go on inbound
                    QTimer.singleShot(0, self.bisector.nightlies_to_inbound)
                else:
                    # no inbound, bisection is done.
                    self.stop()
                return
            msg = "The bisection is done."
            dialog = QMessageBox.information
        dialog(self.mainwindow, "End of the bisection", msg)
        self.stop()
