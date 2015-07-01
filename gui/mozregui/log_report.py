from PyQt4.QtCore import QObject, pyqtSlot as Slot, pyqtSignal as Signal
from PyQt4.QtGui import QPlainTextEdit
from datetime import datetime


class LogView(QPlainTextEdit):
    def __init__(self, parent=None):
        QPlainTextEdit.__init__(self, parent)
        self.setMaximumBlockCount(1000)

    @Slot(dict)
    def on_log_received(self, data):
        time_info = datetime.fromtimestamp((data['time']/1000)).isoformat()
        log_message = '%s: %s : %s' % (
            time_info, data['level'], data['message'])
        self.appendPlainText(log_message)


class LogModel(QObject):
    log = Signal(dict)

    def __call__(self, data):
        self.log.emit(data)
