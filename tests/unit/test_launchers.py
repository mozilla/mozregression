from mozregression import launchers
import unittest
import tempfile
import mozfile
import os
from mock import patch
from mozprofile import FirefoxProfile, Profile

class MyLauncher(launchers.Launcher):
    installed = None
    started = False
    stopped = False

    def _install(self, dest):
        self.installed = dest

    def _start(self):
        self.started = True

    def _stop(self):
        self.stopped = True

class TestLauncher(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        # move on tempdir since launchers without persists
        # download in current dir
        curdir = os.getcwd()
        os.chdir(self.tempdir)
        with open('123-persist.zip', 'w') as f:
            f.write('test-content')
        self.addCleanup(mozfile.rmtree, self.tempdir)
        self.addCleanup(os.chdir, curdir)

    def _fake_download(self, url, dest):
        with open(dest, 'w') as f:
            f.write('test-content')

    @patch('mozregression.launchers.download_url')
    def test_download_on_create(self, download_url):
        download_url.side_effect = self._fake_download
        launcher = MyLauncher('http://fake/file.tar.bz2')
        # download_url was called
        self.assertEqual(download_url.call_args, (('http://fake/file.tar.bz2',
                                                  'file.tar.bz2'),))
        # it is installed
        self.assertEqual(launcher.installed, 'file.tar.bz2')
        # download file was removed
        self.assertFalse(os.path.exists('file.tar.bz2'))

    @patch('mozregression.launchers.download_url')
    def test_persist_download_on_create(self, download_url):
        download_url.side_effect = self._fake_download
        launcher = MyLauncher('http://foo/persist.zip', persist=self.tempdir)
        expected_dest = os.path.join(self.tempdir, 'persist.zip')
        # file has been downloaded
        self.assertEqual(download_url.call_args, (('http://foo/persist.zip',
                                                   expected_dest),))
        # it is installed
        self.assertEqual(launcher.installed, expected_dest)
        # download file was not removed
        self.assertTrue(os.path.exists(expected_dest))

    def test_reuse_persist_file_on_create(self):
        launcher = MyLauncher('http://foo/persist.zip', persist=self.tempdir, persist_prefix='123-')
        expected_dest = os.path.join(self.tempdir, '123-persist.zip')
        # file is installed
        self.assertEqual(launcher.installed, expected_dest)
        # but not removed
        self.assertTrue(os.path.exists('123-persist.zip'))

    def test_start_stop(self):
        launcher = MyLauncher('http://foo/persist.zip', persist=self.tempdir, persist_prefix='123-')
        self.assertFalse(launcher.started)
        launcher.start()
        # now it has been started
        self.assertTrue(launcher.started)
        # restarting won't do anything because it was not stopped
        launcher.started=False
        launcher.start()
        self.assertFalse(launcher.started)
        # stop it, then start it again, this time _start is called again
        launcher.stop()
        launcher.start()
        self.assertTrue(launcher.started)

class TestMozRunnerLauncher(unittest.TestCase):
    @patch('mozregression.launchers.mozinstall')
    @patch('mozregression.launchers.download_url')
    @patch('mozregression.launchers.os.unlink')
    def setUp(self, unlink, download_url, mozinstall):
        mozinstall.get_binary.return_value = '/binary'
        self.launcher = launchers.MozRunnerLauncher('http://binary')
        self.addCleanup(self.launcher.stop)

    def test_installed(self):
        self.assertEqual(self.launcher.binary, '/binary')

    @patch('mozregression.launchers.Runner')
    def test_start_no_args(self, Runner):
        self.launcher.start()
        kwargs = Runner.call_args[1]

        self.assertEqual(kwargs['cmdargs'], ())
        self.assertEqual(kwargs['binary'], '/binary')
        self.assertEqual(kwargs['process_args'], {'processOutputLine': [self.launcher._logger.debug]})
        self.assertIsInstance(kwargs['profile'], Profile)
        # runner is started
        Runner.start.assert_called_once()

    @patch('mozregression.launchers.Runner')
    @patch('mozregression.launchers.MozRunnerLauncher.profile_class')
    def test_start_with_addons(self, profile_class, Runner):
        self.launcher.start(addons=['my-addon'])
        profile_class.assert_called_once_with(addons=['my-addon'])
        # runner is started
        Runner.start.assert_called_once()

    @patch('mozregression.launchers.Runner')
    @patch('mozregression.launchers.MozRunnerLauncher.profile_class')
    def test_start_with_profile_and_addons(self, profile_class, Runner):
        self.launcher.start(profile='my-profile', addons=['my-addon'])
        profile_class.assert_called_once_with(profile='my-profile',
                                              addons=['my-addon'])
        # runner is started
        Runner.start.assert_called_once()

    @patch('mozregression.launchers.Runner')
    @patch('mozregression.launchers.mozversion')
    def test_get_app_infos(self, mozversion, Runner):
        mozversion.get_version.return_value = {'some': 'infos'}
        self.launcher.start()
        self.assertEqual(self.launcher.get_app_info(), {'some': 'infos'})
        mozversion.get_version.assert_called_once_with(binary='/binary')
