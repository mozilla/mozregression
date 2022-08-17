from PySide2.QtCore import QObject, QThread, QTimer, Signal, Slot

from mozregression.download_manager import BuildDownloadManager
from mozregression.errors import LauncherError, MozRegressionError
from mozregression.network import get_http_session
from mozregression.persist_limit import PersistLimit
from mozregression.telemetry import UsageMetrics, send_telemetry_ping
from mozregression.test_runner import create_launcher
from mozregui.global_prefs import apply_prefs, get_prefs
from mozregui.log_report import log


class GuiBuildDownloadManager(QObject, BuildDownloadManager):
    download_progress = Signal(object, int, int)
    download_started = Signal(object)
    download_finished = Signal(object, str)

    def __init__(self, destdir, persist_limit, **kwargs):
        QObject.__init__(self)
        BuildDownloadManager.__init__(
            self, destdir, session=get_http_session(), persist_limit=persist_limit, **kwargs
        )

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

        dl = self.download(build_url, fname, progress=self.download_progress.emit)
        if not dl:
            # file already downloaded.
            # emit the finished signal so bisection goes on
            self.download_finished.emit(None, dest)


class GuiTestRunner(QObject):
    evaluate_started = Signal(str)
    evaluate_finished = Signal()

    def __init__(self):
        QObject.__init__(self)
        self.verdict = None
        self.launcher = None
        self.launcher_kwargs = {}
        self.run_error = False

    def evaluate(self, build_info, allow_back=False):
        try:
            self.launcher = create_launcher(build_info)
            self.launcher.start(**self.launcher_kwargs)
            build_info.update_from_app_info(self.launcher.get_app_info())
        except Exception as exc:
            self.run_error = True
            self.evaluate_started.emit(str(exc))
        else:
            self.evaluate_started.emit("")
            self.run_error = False

    def finish(self, verdict):
        if self.launcher:
            try:
                self.launcher.stop()
            except LauncherError:
                pass  # silently pass stop process error
            self.launcher.cleanup()
        self.verdict = verdict
        if verdict is not None:
            self.evaluate_finished.emit()


class AbstractBuildRunner(QObject):
    """
    Base class to run a build.

    Create the required test runner and build manager, along with a thread
    that should be used for blocking tasks.
    """

    running_state_changed = Signal(bool)
    worker_created = Signal(object)
    worker_class = None

    def __init__(self, mainwindow):
        QObject.__init__(self)
        self.mainwindow = mainwindow
        self.thread = None
        self.worker = None
        self.pending_threads = []
        self.test_runner = None
        self.download_manager = None
        self.options = None
        self.stopped = False

    def init_worker(self, fetch_config, options):
        """
        Create and initialize the worker.

        Should be subclassed to configure the worker, and should return the
        worker method that should start the work.
        """
        self.options = options

        # global preferences
        global_prefs = get_prefs()
        self.global_prefs = global_prefs
        # apply the global prefs now
        apply_prefs(global_prefs)

        fetch_config.set_base_url(global_prefs["archive_base_url"])

        download_dir = global_prefs["persist"]
        if not download_dir:
            download_dir = self.mainwindow.persist
        persist_limit = PersistLimit(abs(global_prefs["persist_size_limit"]) * 1073741824)
        self.download_manager = GuiBuildDownloadManager(download_dir, persist_limit)
        self.test_runner = GuiTestRunner()
        self.thread = QThread()

        # options for the app launcher
        launcher_kwargs = {}
        for name in ("profile", "preferences"):
            if name in options:
                value = options[name]
                if value:
                    launcher_kwargs[name] = value

        # add add-ons paths to the app launcher
        launcher_kwargs["addons"] = options["addons"]
        self.test_runner.launcher_kwargs = launcher_kwargs

        launcher_kwargs["cmdargs"] = []

        if options["profile_persistence"] in ("clone-first", "reuse") or options["profile"]:
            launcher_kwargs["cmdargs"] += ["--allow-downgrade"]

        # Thunderbird will fail to start if passed an URL arg
        if options.get("url") and fetch_config.app_name != "thunderbird":
            launcher_kwargs["cmdargs"] += [options["url"]]

        # Lang only works for firefox-l10n
        if options.get("lang"):
            if options["application"] == "firefox-l10n":
                fetch_config.set_lang(options["lang"])
            else:
                raise MozRegressionError("Invalid lang argument")

        self.worker = self.worker_class(fetch_config, self.test_runner, self.download_manager)
        # Move self.bisector in the thread. This will
        # allow to the self.bisector slots (connected after the move)
        # to be automatically called in the thread.
        self.worker.moveToThread(self.thread)
        self.worker_created.emit(self.worker)

    def start(self, fetch_config, options):
        action = self.init_worker(fetch_config, options)
        assert callable(action), "%s should be callable" % action
        self.thread.start()
        # this will be called in the worker thread.
        QTimer.singleShot(0, action)
        # an action = instance of mozregression usage, so send
        # a usage ping (if telemetry is disabled, it will automatically
        # be discarded)
        send_telemetry_ping(
            UsageMetrics(
                variant="gui",
                appname=fetch_config.app_name,
                build_type=fetch_config.build_type,
                good=options.get("good"),
                bad=options.get("bad"),
                launch=getattr(self.worker, "launch_arg", None),
            )
        )

        self.stopped = False
        self.running_state_changed.emit(True)

    @Slot()
    def stop(self, wait=True):
        self.stopped = True
        if self.options:
            if self.options["profile"] and self.options["profile_persistence"] == "clone-first":
                self.options["profile"].cleanup()
        if self.download_manager:
            self.download_manager.cancel()
        if self.thread:
            self.thread.quit()

        if wait:
            if self.download_manager:
                self.download_manager.wait(raise_if_error=False)
            if self.thread:
                # wait for thread(s) completion - this is the case when
                # user close the application
                self.thread.wait()
                for thread in self.pending_threads:
                    thread.wait()
            self.thread = None
        elif self.thread:
            # do not block, just keep track of the thread - we got here
            # when user uses the stop button.
            self.pending_threads.append(self.thread)
            self.thread.finished.connect(self._remove_pending_thread)

        if self.test_runner:
            self.test_runner.finish(None)
        self.running_state_changed.emit(False)
        log("Stopped")

    @Slot()
    def _remove_pending_thread(self):
        for thread in self.pending_threads[:]:
            if thread.isFinished():
                self.pending_threads.remove(thread)
