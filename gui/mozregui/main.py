# first thing, patch requests lib if required
from mozregui import patch_requests
patch_requests.patch()

# Import PyQt4 classes
import sys
from PyQt4.QtGui import QApplication

from mozlog.structuredlog import set_default_logger, StructuredLogger

from mozregui.log_report import LogModel
from mozregui.check_release import CheckRelease
from mozregui.crash_reporter import CrashReporter
from mozregui.mainwindow import MainWindow


def main():
    logger = StructuredLogger('mozregression-gui')
    set_default_logger(logger)
    # Create a Qt application
    log_model = LogModel()
    logger.add_handler(log_model)
    argv = [sys.argv[0].replace("main.py", "mozregression")] + sys.argv[1:]
    app = QApplication(argv)
    crash_reporter = CrashReporter(app)
    crash_reporter.install()
    app.setOrganizationName('mozilla')
    app.setOrganizationDomain('mozilla.org')
    app.setApplicationName('mozregression-gui')
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


if __name__ == '__main__':
    main()
