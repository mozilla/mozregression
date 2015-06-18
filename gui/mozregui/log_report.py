from PyQt4.QtCore import QObject, pyqtSlot as Slot, pyqtSignal as Signal
from PyQt4.QtGui import QPlainTextEdit, QTextCursor, QColor, \
    QTextCharFormat
from datetime import datetime

COLORS = {
    'DEBUG': QColor(6, 146, 6),         # green
    'INFO': QColor(250, 184, 4),        # deep yellow
    'WARNING': QColor(255, 0, 0, 127),  # red
    'CRITICAL': QColor(255, 0, 0, 127),
    'ERROR': QColor(255, 0, 0, 127),
    }


class LogView(QPlainTextEdit):
    @Slot(dict)
    def on_log_received(self, data):
        time_info = datetime.fromtimestamp((data['time']/1000)).isoformat()
        log_message = '%s: %s : %s' % (
            time_info, data['level'], data['message'])
        message_document = self.document()
        cursor_to_add = QTextCursor(message_document)
        cursor_to_add.movePosition(cursor_to_add.End)
        cursor_to_add.insertText(log_message + '\n')
        if data['level'] in COLORS:
            fmt = QTextCharFormat()
            fmt.setForeground(COLORS[data['level']])
            cursor_to_add.movePosition(cursor_to_add.PreviousBlock)
            cursor_to_add_fmt = message_document.find(data['level'],
                                                      cursor_to_add.position())
            cursor_to_add_fmt.mergeCharFormat(fmt)
        self.ensureCursorVisible()
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
