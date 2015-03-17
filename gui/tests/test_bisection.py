import unittest
import time
import tempfile
import shutil
import os
from mock import Mock, patch
from . import wait_signal

from mozregui import bisection


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
        self.addCleanup(shutil.rmtree, tmpdir)
        self.dl_manager = \
            bisection.GuiBuildDownloadManager(tmpdir, session=self.session)
        self.signals = {}
        for sig in ('download_progress', 'download_started',
                    'download_finished'):
            self.signals[sig] = Mock()
            getattr(self.dl_manager, sig).connect(self.signals[sig])

    @patch('mozregui.bisection.GuiBuildDownloadManager._extract_download_info')
    def test_focus_download(self, extract_info):
        extract_info.return_value = ('http://foo', 'foo')
        mock_response(self.session_response, 'this is some data' * 1000)
        build_info = {}

        with wait_signal(self.dl_manager.download_finished):
            self.dl_manager.focus_download(build_info)

        # build_path is defined
        self.assertEquals(build_info['build_path'],
                          self.dl_manager.get_dest('foo'))

        # signals have been emitted
        self.assertEquals(self.signals['download_started'].call_count, 1)
        self.assertEquals(self.signals['download_finished'].call_count, 1)
        self.assertTrue(self.signals['download_progress'].call_count >= 2)

        # well, file has been downloaded finally
        self.assertTrue(os.path.isfile(build_info['build_path']))


class TestGuiTestRunner(unittest.TestCase):
    def setUp(self):
        self.evaluate_started = Mock()
        self.evaluate_finished = Mock()
        self.test_runner = bisection.GuiTestRunner()
        self.test_runner.evaluate_started.connect(self.evaluate_started)
        self.test_runner.evaluate_finished.connect(self.evaluate_finished)

    @patch('mozregui.bisection.GuiTestRunner.create_launcher')
    def test_basic(self, create_launcher):
        launcher = Mock(get_app_info=lambda: 'app_info')
        create_launcher.return_value = launcher

        # nothing called yet
        self.assertEquals(self.evaluate_started.call_count, 0)
        self.assertEquals(self.evaluate_finished.call_count, 0)

        self.test_runner.evaluate({})

        # now evaluate_started has been called
        self.assertEquals(self.evaluate_started.call_count, 1)
        self.assertEquals(self.evaluate_finished.call_count, 0)
        # launcher and app_info are defined
        self.assertEquals(self.test_runner.launcher, launcher)
        self.assertEquals(self.test_runner.app_info, 'app_info')

        self.test_runner.finish('g')

        # now evaluate_finished has been called
        self.assertEquals(self.evaluate_started.call_count, 1)
        self.assertEquals(self.evaluate_finished.call_count, 1)
        # verdict is defined, launcher is None
        self.assertEquals(self.test_runner.verdict, 'g')
        self.assertIsNone(self.test_runner.launcher)
