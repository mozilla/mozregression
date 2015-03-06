import mozinfo
from PySide.QtCore import QObject, Signal, Slot
from PySide.QtGui import QMessageBox

from mozregression.fetch_configs import create_config
from mozregression.bisector import Bisector, Bisection, NightlyHandler, \
    InboundHandler
from mozregression.download_manager import BuildDownloadManager
from mozregression.test_runner import TestRunner


class GuiBuildDownloadManager(QObject, BuildDownloadManager):
    download_progress = Signal(object, int, int)
    download_started = Signal(object)
    download_finished = Signal(object)

    def __init__(self, destdir):
        QObject.__init__(self)
        BuildDownloadManager.__init__(self, None, destdir)

    def _download_started(self, task):
        self.download_started.emit(task)
        BuildDownloadManager._download_started(self, task)

    def _download_finished(self, task):
        self.download_finished.emit(task)
        BuildDownloadManager._download_finished(self, task)

    def focus_download(self, build_info):
        build_url, fname = self._extract_download_info(build_info)
        dest = self.get_dest(fname)
        # first, stop all downloads in background (except the one for this
        # build if any)
        self.cancel(cancel_if=lambda dl: dest != dl.get_dest())

        dl = self.download(build_url, fname)
        if dl:
            dl.set_progress(self.download_progress.emit)
        build_info['build_path'] = dest


class GuiTestRunner(QObject, TestRunner):
    evaluate_started = Signal()
    evaluate_finished = Signal()

    def __init__(self):
        QObject.__init__(self)
        TestRunner.__init__(self)
        self.app_info = {}
        self.verdict = None
        self.launcher = None
        self.launcher_kwargs = {}

    def evaluate(self, build_info, allow_back=False):
        self.launcher = self.create_launcher(build_info)
        self.launcher.start(**self.launcher_kwargs)
        self.app_info = self.launcher.get_app_info()
        self.evaluate_started.emit()

    def finish(self, verdict):
        assert self.launcher
        self.launcher.stop()
        self.verdict = verdict
        self.evaluate_finished.emit()
        self.launcher = None


class GuiBisector(QObject, Bisector):
    finished = Signal(int)

    def __init__(self, fetch_config, persist=None):
        QObject.__init__(self)
        Bisector.__init__(self, fetch_config, GuiTestRunner(), persist=persist)
        self.download_manager = GuiBuildDownloadManager(self.download_dir)
        self.bisection = None
        self.mid = None
        self.build_infos = None

        self.download_manager.download_finished.connect(self._build_dl_finished)
        self.test_runner.evaluate_finished.connect(self._evaluate_finished)

    def _bisect(self, handler, build_data):
        self.bisection = Bisection(handler, build_data,
                                   self.download_manager, 
                                   self.test_runner,
                                   self.fetch_config,
                                   dl_in_background=False)
        self._bisect_next()

    @Slot()
    def _bisect_next(self):
        # todo: make this non blocking
        self.mid = mid = self.bisection.search_mid_point()
        result = self.bisection.init_handler(mid) 
        if result != Bisection.RUNNING:
            self.finished.emit(result)
        else:
            self.build_infos = \
                self.bisection.handler.build_infos(mid, self.fetch_config)
            self.download_manager.focus_download(self.build_infos)

    @Slot(object)
    def _build_dl_finished(self, dl):
        if not dl.get_dest() == self.build_infos['build_path']:
            return
        if dl.is_canceled() or dl.error():
            # todo handle this
            return
        self.bisection.evaluate(self.build_infos)

    @Slot()
    def _evaluate_finished(self):
        self.bisection.update_build_info(self.mid, self.test_runner.app_info)
        result = self.bisection.handle_verdict(self.mid, self.test_runner.verdict)
        if result != Bisection.RUNNING:
            self.finished.emit(result)
        else:
            self._bisect_next()


class BisectRunner(QObject):
    def __init__(self, mainwindow):
        QObject.__init__(self)
        self.mainwindow = mainwindow
        self.bisector = None

    def bisect(self, options):
        fetch_config = create_config(options['application'],
                                     mozinfo.os, mozinfo.bits)
        self.bisector = GuiBisector(fetch_config)
        self.bisector.download_manager.download_progress.connect(
            self.show_dl_progress)
        self.bisector.test_runner.evaluate_started.connect(
            self.evaluate)
        if options['bisect_type'] == 'nightlies':
            handler = NightlyHandler()
            start = options['start_date']
            end = options['end_date']
        else:
            handler = InboundHandler()
            raise NotImplementedError()
        self.bisector.bisect(handler, start, end)

    @Slot(object, int, int)
    def show_dl_progress(self, dl, current, total):
        message = "downloading %s: %d/%d" % (dl.get_dest(), current, total)
        self.mainwindow.ui.statusbar.showMessage(message, 2000)

    @Slot()
    def evaluate(self):
        res = QMessageBox.question(self.mainwindow,
                                   "Build Evaluation",
                                   "Is that good ?",
                                   buttons=QMessageBox.Yes | QMessageBox.No)
        verdict = "g"
        if res == QMessageBox.No:
            verdict = "b"
        self.bisector.test_runner.finish(verdict)
