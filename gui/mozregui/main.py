# first thing, patch requests lib if required
from mozregui import patch_requests
patch_requests.patch()

# Import PyQt4 classes
import sys  # noqa
from PyQt4.QtGui import QApplication  # noqa

from mozlog.structuredlog import set_default_logger, StructuredLogger  # noqa

from mozregui.log_report import LogModel  # noqa
from mozregui.check_release import CheckRelease  # noqa
from mozregui.crash_reporter import CrashReporter  # noqa
from mozregui.mainwindow import MainWindow  # noqa
from mozregui.global_prefs import set_default_prefs  # noqa

# stupid hack to make sure mozprocess.winprocess, idna.idnadata,
# and SocketServer get bundled despite some bug in cx_Freeze
# (see: https://github.com/anthony-tuininga/cx_Freeze/issues/393)
import os  # noqa
if os.name == 'nt':
    import mozprocess.winprocess
    mywinprocess = mozprocess.winprocess
import idna.idnadata  # noqa
import SocketServer  # noqa


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


if __name__ == '__main__':
    main()
