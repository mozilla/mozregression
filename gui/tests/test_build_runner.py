import os
import tempfile
import time
import unittest

import pytest
from mock import Mock, patch
from PySide2.QtCore import QObject, QThread, Signal, Slot

from mozregression.fetch_configs import create_config
from mozregression.persist_limit import PersistLimit
from mozregui import build_runner


@pytest.fixture(autouse=True)
def mock_send_telemetry_ping():
    with patch("mozregui.build_runner.send_telemetry_ping") as p:
        yield p


def mock_session():
    response = Mock()
    session = Mock(get=Mock(return_value=response))
    return session, response


def mock_response(response, data, wait=0):
    def iter_content(chunk_size=4):
        rest = data
        while rest:
            time.sleep(wait)
            chunk = rest[:chunk_size]
            rest = rest[chunk_size:]
            yield chunk

    response.headers = {"Content-length": str(len(data))}
    response.iter_content = iter_content


class TestGuiTestRunner(unittest.TestCase):
    def setUp(self):
        self.evaluate_started = Mock()
        self.evaluate_finished = Mock()
        self.test_runner = build_runner.GuiTestRunner()
        self.test_runner.evaluate_started.connect(self.evaluate_started)
        self.test_runner.evaluate_finished.connect(self.evaluate_finished)

    @patch("mozregui.build_runner.create_launcher")
    def test_basic(self, create_launcher):
        launcher = Mock(get_app_info=lambda: "app_info")
        create_launcher.return_value = launcher

        # nothing called yet
        self.assertEqual(self.evaluate_started.call_count, 0)
        self.assertEqual(self.evaluate_finished.call_count, 0)

        self.test_runner.evaluate(Mock())

        # now evaluate_started has been called
        self.assertEqual(self.evaluate_started.call_count, 1)
        self.assertEqual(self.evaluate_finished.call_count, 0)
        # launcher is defined
        self.assertEqual(self.test_runner.launcher, launcher)

        self.test_runner.finish("g")

        # now evaluate_finished has been called
        self.assertEqual(self.evaluate_started.call_count, 1)
        self.assertEqual(self.evaluate_finished.call_count, 1)
        # verdict is defined, launcher is None
        self.assertEqual(self.test_runner.verdict, "g")


@pytest.fixture()
def mock_extract_info():
    with patch("mozregui.build_runner.GuiBuildDownloadManager._extract_download_info") as p:
        yield p


def test_gui_build_download_manager_focus_download(qtbot, mock_extract_info):
    session, session_response = mock_session()
    with tempfile.TemporaryDirectory() as tmpdir:
        tpersist = PersistLimit(10 * 1073741824)
        dl_manager = build_runner.GuiBuildDownloadManager(tmpdir, tpersist)
        dl_manager.session = session
        signals = {}
        for sig in ("download_progress", "download_started", "download_finished"):
            signals[sig] = Mock()
            getattr(dl_manager, sig).connect(signals[sig])

        mock_extract_info.return_value = ("http://foo", "foo")
        mock_response(session_response, b"this is some data" * 10000, 0.01)
        build_info = Mock()

        with qtbot.waitSignal(dl_manager.download_finished, raising=True):
            dl_manager.focus_download(build_info)

        # build_path is defined
        assert build_info.build_file == dl_manager.get_dest("foo")

        # signals have been emitted
        assert signals["download_started"].call_count == 1
        assert signals["download_finished"].call_count == 1
        assert signals["download_progress"].call_count == 12

        # well, file has been downloaded finally
        assert os.path.isfile(build_info.build_file)


def test_abstract_build_runner(qtbot):
    main_thread = QThread.currentThread()

    class Worker(QObject):
        call_started = Signal()

        def __init__(self, *args):
            QObject.__init__(self)

        @Slot()
        def my_slot(self):
            assert main_thread != self.thread()
            self.call_started.emit()

    class BuildRunner(build_runner.AbstractBuildRunner):
        call_started = Signal()
        thread_finished = Signal()
        worker_class = Worker

        def init_worker(self, fetch_config, options):
            build_runner.AbstractBuildRunner.init_worker(self, fetch_config, options)
            self.thread.finished.connect(self.thread_finished)
            self.worker.call_started.connect(self.call_started)
            return self.worker.my_slot

    # instantiate the runner
    runner = BuildRunner(Mock(persist="."))

    assert not runner.thread

    with qtbot.waitSignal(runner.thread_finished, raising=True):
        with qtbot.waitSignal(runner.call_started, raising=True):
            runner.start(
                create_config("firefox", "linux", 64, "x86_64"),
                {"addons": (), "profile": "/path/to/profile", "profile_persistence": "clone"},
            )

        runner.stop(True)

    assert not runner.pending_threads


def test_runner_started_multiple_times(mock_send_telemetry_ping):
    class Worker(QObject):
        def __init__(self, *args):
            QObject.__init__(self)

    class BuildRunner(build_runner.AbstractBuildRunner):
        worker_class = Worker

        def init_worker(self, fetch_config, options):
            build_runner.AbstractBuildRunner.init_worker(self, fetch_config, options)
            return lambda: 1

    fetch_config = create_config("firefox", "linux", 64, "x86_64")
    options = {
        "addons": (),
        "profile": "/path/to/profile",
        "profile_persistence": "clone",
    }

    runner = BuildRunner(Mock(persist="."))
    assert not runner.stopped
    runner.start(fetch_config, options)
    assert mock_send_telemetry_ping.call_count == 1
    assert not runner.stopped
    runner.stop()
    assert runner.stopped
    runner.start(fetch_config, options)
    assert mock_send_telemetry_ping.call_count == 2
    assert not runner.stopped
    runner.stop()
    assert runner.stopped
