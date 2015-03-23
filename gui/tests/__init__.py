from PyQt4.QtGui import QApplication
from PyQt4.QtCore import QEventLoop, QTimer
from contextlib import contextmanager

APP = QApplication([])  # we need an application to create widgets


@contextmanager
def wait_signal(signal, timeout=1):
    """Block loop until signal emitted, or timeout (s) elapses."""
    loop = QEventLoop()
    signal.connect(loop.quit)

    yield

    timed_out = []
    if timeout is not None:
        def quit_with_error():
            timed_out.append(1)
            loop.quit()
        QTimer.singleShot(timeout * 1000, quit_with_error)
    loop.exec_()
    if timed_out:
        assert False, "Timeout while waiting for %s" % signal
