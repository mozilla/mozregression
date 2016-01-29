from PyQt4.QtCore import QObject, pyqtSlot as Slot, pyqtSignal as Signal
from PyQt4.QtGui import (QPlainTextEdit, QTextCursor, QColor,
                         QTextCharFormat, QMenu, QAction,
                         QTextBlockUserData, QActionGroup)
from datetime import datetime
from mozlog.structuredlog import log_levels

from mozlog import get_default_logger

COLORS = {
    'DEBUG': QColor(6, 146, 6),  # green
    'INFO': QColor(250, 184, 4),  # deep yellow
    'WARNING': QColor(255, 0, 0, 127),  # red
    'CRITICAL': QColor(255, 0, 0, 127),
    'ERROR': QColor(255, 0, 0, 127),
}


class LogLevelData(QTextBlockUserData):
    def __init__(self, log_lvl):
        QTextBlockUserData.__init__(self)
        self.log_lvl = log_lvl


class LogView(QPlainTextEdit):
    def __init__(self, parent=None):
        QPlainTextEdit.__init__(self, parent)
        self.setMaximumBlockCount(1000)

        self.group = QActionGroup(self)
        self.actions = [QAction(log_lvl, self.group) for log_lvl in
                        ["Debug", "Info", "Warning", "Error", "Critical"]]

        for action in self.actions:
            action.setCheckable(True)
            action.triggered.connect(self.on_log_filter)
        self.actions[0].setChecked(True)

        self.customContextMenuRequested.connect(
            self.on_custom_context_menu_requested)

        self.log_lvl = log_levels["DEBUG"]

    def text_blocks(self):
        current_block = QTextCursor(self.document()).block()
        while current_block.isValid and current_block.text():
            yield current_block
            current_block = current_block.next()

    @Slot(dict)
    def on_log_received(self, data):
        time_info = datetime.fromtimestamp((data['time'] / 1000)).isoformat()
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
            if log_levels[data['level']] > self.log_lvl:
                cursor_to_add.block().setVisible(False)
        self.ensureCursorVisible()

    @Slot()
    def on_custom_context_menu_requested(self):
        menu = QMenu(self)
        for action in self.actions:
            menu.addAction(action)
        menu.popup(self.cursor().pos())

    @Slot()
    def on_log_filter(self):
        log_lvl_name = str(self.sender().iconText()).upper()
        self.log_lvl = log_levels[log_lvl_name]
        cursor = QTextCursor(self.document())
        current_block = cursor.block()
        while current_block.isValid() and current_block.userData():
            block_log_lvl = current_block.userData().log_lvl
            if block_log_lvl <= self.log_lvl:
                current_block.setVisible(True)
            else:
                current_block.setVisible(False)
            current_block = current_block.next()
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
