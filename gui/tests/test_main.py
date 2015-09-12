import os
import unittest
from mock import patch
from PyQt4.QtCore import QTimer
from . import APP

from mozregui import main  # noqa


class TestMain(unittest.TestCase):
    @patch('mozregui.main.QApplication')
    @patch('mozregui.main.CheckRelease')
    @patch("mozregui.main.CrashReporter")
    def run_app(self, func, _1, _2, QApplication):
        QApplication.return_value = APP

        def _quit():
            # first close all the widgets, else the quit() method
            # does not work if we have some modal widgets (like the wizard)
            for w in APP.topLevelWidgets():
                w.close()
            # wait for the widgets to be really closed, then call quit.
            QTimer.singleShot(100, APP.quit)

        QTimer.singleShot(0, func)
        QTimer.singleShot(20, _quit)
        with self.assertRaises(SystemExit):
            main.main()

    def test_persist_is_created_and_deleted(self):
        data = {
            'persist_dir': None,
            'created': None,
            'deleted': None,
        }

        def check_persist_is_created():
            main_win = None

            for w in APP.topLevelWidgets():
                if isinstance(w, main.MainWindow):
                    main_win = w
                    break

            data['persist_dir'] = main_win.persist
            data['created'] = os.path.isdir(data['persist_dir'])

        self.run_app(check_persist_is_created)
        data['deleted'] = not os.path.isdir(data['persist_dir'])

        self.assertTrue(data['created'])
        self.assertTrue(data['deleted'])
