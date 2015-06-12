from PyQt4.QtCore import QObject, pyqtSlot as Slot, pyqtSignal as Signal
from PyQt4.QtGui import QPlainTextEdit, QTextCursor
from datetime import datetime


class LogView(QPlainTextEdit):
    @Slot(dict)
    def on_log_received(self, data):
        time_info = datetime.fromtimestamp((data['time']/1000)).isoformat()
        log_message = '%s: %s : %s' % (
            time_info, data['level'], data['message'])
        self.appendPlainText(log_message)
        counter = self.blockCount()

        # do not display more than 1000 log lines
        if counter > 1000:
            document = self.document()
            cursor = QTextCursor(document.findBlockByLineNumber(0))
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.deleteChar()
            cursor.deleteChar()


class LogModel(QObject):
    log = Signal(dict)

    def __call__(self, data):
        self.log.emit(data)
