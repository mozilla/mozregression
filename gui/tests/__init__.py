from PySide.QtGui import QApplication
from PySide.QtCore import QEventLoop, QTimer
from contextlib import contextmanager

APP = QApplication([])  # we need an application to create widgets


@contextmanager
def wait_signal(signal, timeout=1):
    """Block loop until signal emitted, or timeout (s) elapses."""
    loop = QEventLoop()
    signal.connect(loop.quit)

    yield

    if timeout is not None:
        def quit_with_error():
            loop.quit()
            assert False, "Timeout while waiting for %s" % signal
        QTimer.singleShot(timeout * 1000, quit_with_error)
    loop.exec_()
