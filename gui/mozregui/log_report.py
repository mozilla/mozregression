from PyQt4.QtCore import QObject, pyqtSlot as Slot, pyqtSignal as Signal
from PyQt4.QtGui import QPlainTextEdit, QTextCursor, QColor, \
    QTextCharFormat, QMenu
from datetime import datetime
from mozlog import get_default_logger

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

        self.contextMenu = QMenu(parent=self)
        self.contextMenu.addAction("Debug")
        self.contextMenu.addAction("Info")
        self.contextMenu.addAction("Warning")
        self.contextMenu.addAction("Critical")
        self.contextMenu.addAction("Error")
        self.customContextMenuRequested.connect(self.on_custom_context_menu_requested)

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

    @Slot(dict)
    def on_custom_context_menu_requested(self, pos):
        self.contextMenu.move(self.cursor().pos())
        self.contextMenu.show()


class LogModel(QObject):
    log = Signal(dict)

    def __call__(self, data):
        self.log.emit(data)


def log(text, log=True, status_bar=True, status_bar_timeout=2.0):
    if log:
        logger = get_default_logger('mozregui')
        if logger:
            logger.info(text)
    if status_bar:
        from mozregui.mainwindow import MainWindow
        mw = MainWindow.INSTANCE
        if mw:
            mw.ui.status_bar.showMessage(text, int(status_bar_timeout * 1000))

