import sys

from mozlog.structuredlog import StructuredLogger, set_default_logger
from PySide2.QtCore import Qt
from PySide2.QtWidgets import QApplication

from mozregression.log import init_python_redirect_logger

from .check_release import CheckRelease
from .crash_reporter import CrashReporter
from .global_prefs import set_default_prefs
from .log_report import LogModel
from .mainwindow import MainWindow


def main():
    logger = StructuredLogger("mozregression-gui")
    init_python_redirect_logger(logger)
    set_default_logger(logger)

    # Create a Qt application
    log_model = LogModel()
    logger.add_handler(log_model)
    argv = [sys.argv[0].replace("mozregression-gui.py", "mozregression")] + sys.argv[1:]

    # enable hi-dpi scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

    app = QApplication(argv)
    crash_reporter = CrashReporter(app)
    crash_reporter.install()
    app.setOrganizationName("mozilla")
    app.setOrganizationDomain("mozilla.org")
    app.setApplicationName("mozregression-gui")
    set_default_prefs()
    # Create the main window and show it
    win = MainWindow()
    app.aboutToQuit.connect(win.bisect_runner.stop)
    app.aboutToQuit.connect(win.single_runner.stop)
    app.aboutToQuit.connect(win.clear)
    release_checker = CheckRelease(win)
    release_checker.check()
    log_model.log.connect(win.ui.log_view.on_log_received)
    win.show()
    # Enter Qt application main loop
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
