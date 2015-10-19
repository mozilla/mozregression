from PyQt4.QtCore import QObject, pyqtSlot as Slot, pyqtSignal as Signal
from PyQt4.QtGui import QPlainTextEdit, QTextCursor, QColor, \
    QTextCharFormat
from datetime import datetime
from logging import Handler, LogRecord

COLORS = {
    'DEBUG': QColor(6, 146, 6),         # green
    'INFO': QColor(250, 184, 4),        # deep yellow
    'WARNING': QColor(255, 0, 0, 127),  # red
    'CRITICAL': QColor(255, 0, 0, 127),
    'ERROR': QColor(255, 0, 0, 127),
    }


class LogView(QPlainTextEdit):
    def __init__(self, parent=None):
        QPlainTextEdit.__init__(self, parent)
        self.setMaximumBlockCount(1000)

    @Slot(dict)
    def on_log_received(self, record):
        time_info = datetime.fromtimestamp((record.created/1000)).isoformat()
        log_message = '%s: %s : %s' % (
            time_info, record.levelname, record.getMessage())
        message_document = self.document()
        cursor_to_add = QTextCursor(message_document)
        cursor_to_add.movePosition(cursor_to_add.End)
        cursor_to_add.insertText(log_message + '\n')
        if record.levelname in COLORS:
            fmt = QTextCharFormat()
            fmt.setForeground(COLORS[record.levelname])
            cursor_to_add.movePosition(cursor_to_add.PreviousBlock)
            cursor_to_add_fmt = message_document.find(record.levelname,
                                                      cursor_to_add.position())
            cursor_to_add_fmt.mergeCharFormat(fmt)
        self.ensureCursorVisible()


class QLogModel(QObject):
    log = Signal(LogRecord)


class LogModel(QObject, Handler):
    def __init__(self):
        Handler.__init__(self)
        self.qlog = QLogModel()

    def emit(self, record):
        self.qlog.log.emit(record)
