import sys
import threading

from PySide2.QtCore import QObject, QTimer, Signal, Slot
from PySide2.QtWidgets import QMessageBox

from mozregression.approx_persist import ApproxPersistChooser
from mozregression.bisector import (
    Bisection,
    Bisector,
    IndexPromise,
    IntegrationHandler,
    NightlyHandler,
)
from mozregression.config import DEFAULT_EXPAND
from mozregression.dates import is_date_or_datetime
from mozregression.errors import MozRegressionError
from mozregui.build_runner import AbstractBuildRunner
from mozregui.log_report import log
from mozregui.skip_chooser import SkipDialog

Bisection.EXCEPTION = -1  # new possible value of bisection end


class GuiBisector(QObject, Bisector):
    started = Signal()
    finished = Signal(object, int)
    choose_next_build = Signal()
    step_started = Signal(object)
    step_build_found = Signal(object, object)
    step_testing = Signal(object, object)
    step_finished = Signal(object, str)
    handle_merge = Signal(object, str, str, str)

    def __init__(self, fetch_config, test_runner, download_manager, download_in_background=True):
        QObject.__init__(self)
        Bisector.__init__(self, fetch_config, test_runner, download_manager)
        self.bisection = None
        self.mid = None
        self.build_infos = None
        self._bisect_args = None
        self.error = None
        self._next_build_index = None
        self.download_in_background = download_in_background
        self.index_promise = None
        self._persist_files = ()
        self.should_stop = threading.Event()

        self.download_manager.download_finished.connect(self._build_dl_finished)
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
    def bisect_further(self):
        assert self.bisection
        self.started.emit()
        handler = self.bisection.handler
        try:
            nhandler = IntegrationHandler(find_fix=self.bisection.handler.find_fix)
            Bisector.bisect(
                self,
                nhandler,
                handler.good_revision,
                handler.bad_revision,
                expand=DEFAULT_EXPAND,
                interrupt=self.should_stop.is_set,
            )
        except MozRegressionError:
            self._finish_on_exception(None)
        except StopIteration:
            self.finished.emit(None, Bisection.USER_EXIT)

    @Slot()
    def check_merge(self):
        handler = self.bisection.handler
        try:
            result = handler.handle_merge()
        except MozRegressionError:
            self._finish_on_exception(None)
            return
        if result is None:
            self.bisection.no_more_merge = True
            self.finished.emit(self.bisection, Bisection.FINISHED)
        else:
            self.handle_merge.emit(self.bisection, *result)

    def _bisect(self, handler, build_range):
        self.bisection = Bisection(
            handler,
            build_range,
            self.download_manager,
            self.test_runner,
            dl_in_background=False,
            approx_chooser=self.approx_chooser,
        )
        self._bisect_next()

    @Slot()
    def _bisect_next(self):
        # this is executed in the working thread
        if self.test_runner.verdict != "r":
            try:
                self.mid = self.bisection.search_mid_point(interrupt=self.should_stop.is_set)
            except MozRegressionError:
                self._finish_on_exception(self.bisection)
                return
            except StopIteration:
                return

        # if our last answer was skip, and that the next build
        # to use is not chosen yet, ask to choose it.
        if (
            self._next_build_index is None
            and self.test_runner.verdict == "s"
            and len(self.bisection.build_range) > 3
        ):
            self.choose_next_build.emit()
            return

        if self._next_build_index is not None:
            # here user asked for specific build (eg from choose_next_build)
            self.mid = self._next_build_index
            # this will download build infos if required
            if self.bisection.build_range[self.mid] is False:
                # in case no build info is found, ask to choose again
                self.choose_next_build.emit()
                return
            self._next_build_index = None

        self.step_started.emit(self.bisection)
        result = self.bisection.init_handler(self.mid)
        if result != Bisection.RUNNING:
            self.finished.emit(self.bisection, result)
        else:
            self.build_infos = self.bisection.handler.build_range[self.mid]
            (
                found,
                self.mid,
                self.build_infos,
                self._persist_files,
            ) = self.bisection._find_approx_build(self.mid, self.build_infos)
            if not found:
                self.download_manager.focus_download(self.build_infos)
            self.step_build_found.emit(self.bisection, self.build_infos)
            if found:
                # to continue the bisection, act as if it was downloaded
                self._build_dl_finished(None, self.build_infos.build_file)

    @Slot()
    def _evaluate(self):
        # this is called in the working thread, so installation does not
        # block the ui.

        # download in background, if desired and that last verdict was not
        # a skip.
        if self.download_in_background and self.test_runner.verdict != "s":
            self.index_promise = IndexPromise(
                self.mid,
                self.bisection._download_next_builds,
                args=(self._persist_files,),
            )
        # run the build evaluation
        self.bisection.evaluate(self.build_infos)
        # wait for the next index in the thread if any
        if self.index_promise:
            self.index_promise()
            # if there was an error, stop the possible downloads
            if self.test_runner.run_error:
                self.download_manager.cancel()
                self.download_manager.wait(raise_if_error=False)
        if not self.test_runner.run_error:
            self.step_testing.emit(self.bisection, self.build_infos)

    @Slot(object, str)
    def _build_dl_finished(self, dl, dest):
        # here we are not in the working thread, since the connection was
        # done in the constructor
        if not dest == self.build_infos.build_file:
            return
        if dl is not None and (dl.is_canceled() or dl.error()):
            # todo handle this
            return
        # call this in the thread
        QTimer.singleShot(0, self._evaluate)

    @Slot()
    def _evaluate_finished(self):
        # here we are not in the working thread, since the connection was
        # done in the constructor
        if self.index_promise:
            self.mid = self.index_promise()
            self.index_promise = None

        self.step_finished.emit(self.bisection, self.test_runner.verdict)
        result = self.bisection.handle_verdict(self.mid, self.test_runner.verdict)
        if result != Bisection.RUNNING:
            self.finished.emit(self.bisection, result)
        else:
            # call this in the thread
            QTimer.singleShot(0, self._bisect_next)


class BisectRunner(AbstractBuildRunner):
    worker_class = GuiBisector

    def init_worker(self, fetch_config, options):
        AbstractBuildRunner.init_worker(self, fetch_config, options)

        self.worker.test_runner.evaluate_started.connect(self.evaluate)
        self.worker.finished.connect(self.bisection_finished)
        self.worker.handle_merge.connect(self.handle_merge)
        self.worker.choose_next_build.connect(self.choose_next_build)
        good, bad = options.get("good"), options.get("bad")
        if (
            is_date_or_datetime(good)
            and is_date_or_datetime(bad)
            and fetch_config.should_use_archive()
        ):
            handler = NightlyHandler(find_fix=options["find_fix"])
        else:
            handler = IntegrationHandler(find_fix=options["find_fix"])

        self.worker._bisect_args = (handler, good, bad)
        self.worker.download_in_background = self.global_prefs["background_downloads"]
        if self.global_prefs["approx_policy"]:
            self.worker.approx_chooser = ApproxPersistChooser(7)
        return self.worker.bisect

    def stop(self, wait=True):
        if self.worker:
            self.worker.should_stop.set()
        AbstractBuildRunner.stop(self, wait=wait)

    @Slot(str)
    def evaluate(self, err_message):
        if self.stopped:
            self.test_runner.finish(None)
            return
        if err_message:
            QMessageBox.warning(
                self.mainwindow,
                "Launcher Error",
                (
                    "An error occured while starting the process, so the build"
                    " will be skipped. Error message:<br><strong>%s</strong>" % err_message
                ),
            )
            self.worker.test_runner.finish("s")

    @Slot(str)
    def set_verdict(self, verdict):
        self.worker.test_runner.finish(verdict)

    def open_evaluate_editor(self, open, index):
        if open:
            self.mainwindow.ui.report_view.openPersistentEditor(index)
        else:
            self.mainwindow.ui.report_view.closePersistentEditor(index)

    @Slot()
    def choose_next_build(self):
        dlg = SkipDialog(self.worker.bisection.build_range, self.mainwindow)
        index = dlg.choose_next_build()
        if index is None:
            self.stop()
            return
        self.worker._next_build_index = index
        QTimer.singleShot(0, self.worker._bisect_next)

    @Slot(object, int)
    def bisection_finished(self, bisection, resultcode):
        dialog = None
        if resultcode == Bisection.USER_EXIT:
            msg = "Bisection stopped."
        elif resultcode == Bisection.NO_DATA:
            msg = "Unable to find enough data to bisect."
            dialog = QMessageBox.warning
        elif resultcode == Bisection.EXCEPTION:
            msg = "Error: %s" % self.worker.error[1]
            dialog = QMessageBox.critical
        else:
            fetch_config = self.worker.fetch_config
            if fetch_config.can_go_integration() and not getattr(bisection, "no_more_merge", False):
                if isinstance(bisection.handler, NightlyHandler):
                    handler = bisection.handler
                    fetch_config.set_repo(fetch_config.get_nightly_repo(handler.bad_date))
                    QTimer.singleShot(0, self.worker.bisect_further)
                else:
                    # check merge, try to bisect further
                    QTimer.singleShot(0, self.worker.check_merge)
                return
            msg = "The bisection is done."
        if dialog:
            dialog(self.mainwindow, "End of the bisection", msg)
        else:
            log(msg)
        self.stop()

    @Slot(object, str, str, str)
    def handle_merge(self, bisection, branch, good_rev, bad_rev):
        self.worker.fetch_config.set_repo(str(branch))
        bisection.handler.good_revision = str(good_rev)
        bisection.handler.bad_revision = str(bad_rev)
        QTimer.singleShot(0, self.worker.bisect_further)
