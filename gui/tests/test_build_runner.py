import unittest
import time
import tempfile
import shutil
import os

from mock import Mock, patch
from . import wait_signal
from PyQt4.QtCore import QObject, QThread, pyqtSignal as Signal, \
    pyqtSlot as Slot

from mozregui import build_runner
from mozregression.persist_limit import PersistLimit
from mozregression.fetch_configs import create_config


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

    response.headers = {'Content-length': str(len(data))}
    response.iter_content = iter_content


class TestGuiBuildDownloadManager(unittest.TestCase):
    def setUp(self):
        self.session, self.session_response = mock_session()
        tmpdir = tempfile.mkdtemp()
        tpersist_size = PersistLimit(10 * 1073741824)
        self.addCleanup(shutil.rmtree, tmpdir)
        self.dl_manager = \
            build_runner.GuiBuildDownloadManager(tmpdir, tpersist_size)
        self.dl_manager.session = self.session
        self.signals = {}
        for sig in ('download_progress', 'download_started',
                    'download_finished'):
            self.signals[sig] = Mock()
            getattr(self.dl_manager, sig).connect(self.signals[sig])

    @patch(
        'mozregui.build_runner.GuiBuildDownloadManager._extract_download_info')
    def test_focus_download(self, extract_info):
        extract_info.return_value = ('http://foo', 'foo')
        mock_response(self.session_response, 'this is some data' * 10000, 0.01)
        build_info = Mock()

        with wait_signal(self.dl_manager.download_finished):
            self.dl_manager.focus_download(build_info)

        # build_path is defined
        self.assertEquals(build_info.build_file,
                          self.dl_manager.get_dest('foo'))

        # signals have been emitted
        self.assertEquals(self.signals['download_started'].call_count, 1)
        self.assertEquals(self.signals['download_finished'].call_count, 1)
        self.assertTrue(self.signals['download_progress'].call_count >= 2)

        # well, file has been downloaded finally
        self.assertTrue(os.path.isfile(build_info.build_file))


class TestGuiTestRunner(unittest.TestCase):
    def setUp(self):
        self.evaluate_started = Mock()
        self.evaluate_finished = Mock()
        self.test_runner = build_runner.GuiTestRunner()
        self.test_runner.evaluate_started.connect(self.evaluate_started)
        self.test_runner.evaluate_finished.connect(self.evaluate_finished)

    @patch('mozregui.build_runner.create_launcher')
    def test_basic(self, create_launcher):
        launcher = Mock(get_app_info=lambda: 'app_info')
        create_launcher.return_value = launcher

        # nothing called yet
        self.assertEquals(self.evaluate_started.call_count, 0)
        self.assertEquals(self.evaluate_finished.call_count, 0)

        self.test_runner.evaluate(Mock())

        # now evaluate_started has been called
        self.assertEquals(self.evaluate_started.call_count, 1)
        self.assertEquals(self.evaluate_finished.call_count, 0)
        # launcher is defined
        self.assertEquals(self.test_runner.launcher, launcher)

        self.test_runner.finish('g')

        # now evaluate_finished has been called
        self.assertEquals(self.evaluate_started.call_count, 1)
        self.assertEquals(self.evaluate_finished.call_count, 1)
        # verdict is defined, launcher is None
        self.assertEquals(self.test_runner.verdict, 'g')


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
            build_runner.AbstractBuildRunner.init_worker(self, fetch_config,
                                                         options)
            self.thread.finished.connect(self.thread_finished)
            self.worker.call_started.connect(self.call_started)
            return self.worker.my_slot

    # instantiate the runner
    runner = BuildRunner(Mock(persist='.'))

    assert not runner.thread

    with qtbot.waitSignal(runner.thread_finished, raising=True):
        with qtbot.waitSignal(runner.call_started, raising=True):
            runner.start(
                create_config('firefox', 'linux', 64),
                {'addons': (), 'profile': '/path/to/profile',
                    'profile_persistence': 'clone'},
            )

        runner.stop(True)

    assert not runner.pending_threads


def test_runner_started_multiple_times():
    class Worker(QObject):
        def __init__(self, *args):
            QObject.__init__(self)

    class BuildRunner(build_runner.AbstractBuildRunner):
        worker_class = Worker

        def init_worker(self, fetch_config, options):
            build_runner.AbstractBuildRunner.init_worker(self, fetch_config,
                                                         options)
            return lambda: 1

    fetch_config = create_config('firefox', 'linux', 64)
    options = {'addons': (), 'profile': '/path/to/profile',
               'profile_persistence': 'clone'}

    runner = BuildRunner(Mock(persist='.'))
    assert not runner.stopped
    runner.start(fetch_config, options)
    assert not runner.stopped
    runner.stop()
    assert runner.stopped
    runner.start(fetch_config, options)
    assert not runner.stopped
    runner.stop()
    assert runner.stopped
