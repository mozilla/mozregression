import os
import tempfile

from mock import patch
from PySide6.QtCore import QTimer

from mozregui import main  # noqa

from . import APP


@patch("mozregui.main.QApplication")
@patch("mozregui.main.CheckRelease")
@patch("mozregui.main.CrashReporter")
def run_app(func, _1, _2, QApplication):
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
    try:
        main.main()
    except SystemExit:
        pass


def test_persist_is_created_lazily_and_deleted():
    data = {
        "persist_dir": None,
        "created_at_startup": None,
        "deleted": None,
    }

    def check_persist_is_lazy():
        main_win = None

        for w in APP.topLevelWidgets():
            if isinstance(w, main.MainWindow):
                main_win = w
                break

        data["created_at_startup"] = main_win.persist is not None
        # what a build runner does on first use
        main_win.persist = data["persist_dir"] = tempfile.mkdtemp()

    run_app(check_persist_is_lazy)
    data["deleted"] = not os.path.isdir(data["persist_dir"])

    assert not data["created_at_startup"]
    assert data["deleted"]
