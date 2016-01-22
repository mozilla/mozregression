from PyQt4.QtCore import QObject, pyqtSlot as Slot, pyqtSignal as Signal
from PyQt4.QtGui import QMessageBox

from mozregression.errors import MozRegressionError
from mozregression.dates import is_date_or_datetime
from mozregression.fetch_build_info import (NightlyInfoFetcher,
                                            InboundInfoFetcher)

from mozregui.build_runner import AbstractBuildRunner


class SingleBuildWorker(QObject):
    started = Signal()
    step_testing = Signal(object, object)
    step_build_found = Signal(object, object)
    error = Signal(object)

    def __init__(self, fetch_config, test_runner, download_manager):
        QObject.__init__(self)
        self.fetch_config = fetch_config
        self.test_runner = test_runner
        self.download_manager = download_manager
        self.launch_arg = None
        self._build_info = None

    def _find_build_info(self, fetcher_class):
        self.started.emit()
        fetcher = fetcher_class(self.fetch_config)
        try:
            self._build_info = fetcher.find_build_info(self.launch_arg)
        except MozRegressionError as exc:
            self.error.emit(exc)
            return
        self.step_build_found.emit(self, self._build_info)
        self.download_manager.focus_download(self._build_info)

    @Slot()
    def launch_nightlies(self):
        self._find_build_info(NightlyInfoFetcher)

    @Slot()
    def launch_inbounds(self):
        self._find_build_info(InboundInfoFetcher)

    @Slot(object, str)
    def _on_downloaded(self, dl, dest):
        if not dest == self._build_info.build_file:
            return
        if dl is not None and (dl.is_canceled() or dl.error()):
            # todo handle this
            return
        self.step_testing.emit(self, self._build_info)
        self.test_runner.evaluate(self._build_info)


class SingleBuildRunner(AbstractBuildRunner):
    worker_class = SingleBuildWorker

    def init_worker(self, fetch_config, options):
        AbstractBuildRunner.init_worker(self, fetch_config, options)
        self.download_manager.download_finished.connect(
            self.worker._on_downloaded)
        self.worker.launch_arg = options.pop('launch')
        # evaluate_started will be called if we have an error
        self.test_runner.evaluate_started.connect(self.on_error)
        self.worker.error.connect(self.on_error)
        if is_date_or_datetime(self.worker.launch_arg) and \
           not fetch_config.should_use_taskcluster():
            return self.worker.launch_nightlies
        else:
            return self.worker.launch_inbounds

    @Slot(object)
    def on_error(self, error):
        if error:
            self.stop(wait=False)
            QMessageBox.critical(self.mainwindow, "Error", unicode(error))
