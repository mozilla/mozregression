from PyQt4.QtCore import QObject, pyqtSlot as Slot, pyqtSignal as Signal
from PyQt4.QtGui import QPlainTextEdit, QTextCursor, QColor, \
    QTextCharFormat, QMenu, QAction, QTextBlock, QTextBlockUserData
from datetime import datetime
from mozlog.structuredlog import log_levels

from mozlog import get_default_logger

COLORS = {
    'DEBUG': QColor(6, 146, 6),         # green
    'INFO': QColor(250, 184, 4),        # deep yellow
    'WARNING': QColor(255, 0, 0, 127),  # red
    'CRITICAL': QColor(255, 0, 0, 127),
    'ERROR': QColor(255, 0, 0, 127),
    }

log_names_to_levels = {v:k for k,v in log_levels.iteritems()}

class LogLevelData(QTextBlockUserData):
    def __init__(self, log_lvl):
        QTextBlockUserData.__init__(self)
        self.log_lvl = log_lvl


class LogView(QPlainTextEdit):
    def __init__(self, parent=None):
        QPlainTextEdit.__init__(self, parent)
        self.setMaximumBlockCount(1000)

        self.contextMenu = QMenu(parent=self)

        debugFilterAction = QAction("Debug", self.contextMenu)
        infoFilterAction = QAction("Info", self.contextMenu)
        warningFilterAction = QAction("Warning", self.contextMenu)
        criticalFilterAction = QAction("Critical", self.contextMenu)
        errorFilterAction = QAction("Error", self.contextMenu)

        self.contextMenu.addAction(debugFilterAction)
        self.contextMenu.addAction(infoFilterAction)
        self.contextMenu.addAction(warningFilterAction)
        self.contextMenu.addAction(criticalFilterAction)
        self.contextMenu.addAction(errorFilterAction)

        self.customContextMenuRequested.connect(self.on_custom_context_menu_requested)
        debugFilterAction.triggered.connect(self.on_log_filter)
        infoFilterAction.triggered.connect(self.on_log_filter)
        warningFilterAction.triggered.connect(self.on_log_filter)
        criticalFilterAction.triggered.connect(self.on_log_filter)
        errorFilterAction.triggered.connect(self.on_log_filter)

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
            log_lvl_data = LogLevelData(log_levels[data['level'].upper()])
            cursor_to_add.block().setUserData(log_lvl_data)
            cursor_to_add_fmt = message_document.find(data['level'],
                                                      cursor_to_add.position())
            cursor_to_add_fmt.mergeCharFormat(fmt)
        self.ensureCursorVisible()

    @Slot()
    def on_custom_context_menu_requested(self):
        self.contextMenu.move(self.cursor().pos())
        self.contextMenu.show()

    @Slot()
    def on_log_filter(self):
        log_lvl_name = str(self.sender().iconText()).upper()
        log_lvl = log_levels[log_lvl_name]
        cursor = QTextCursor(self.document())
        current_block = cursor.block()
        while True:
            if current_block.userData():
                block_log_lvl = current_block.userData().log_lvl
                if block_log_lvl <= log_lvl:
                    current_block.setVisible(True)
                else:
                    current_block.setVisible(False)
                current_block = current_block.next()
            else:
                break
        self.viewport().update()


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

