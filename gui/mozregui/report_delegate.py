from PyQt4.QtGui import QStyledItemDelegate, QStyleOptionProgressBarV2, \
    QApplication, QStyle, QWidget, QPainter, QIcon, QPixmap
from PyQt4.QtCore import Qt, QRect, pyqtSignal as Signal

from mozregui.ui.ask_verdict import Ui_AskVerdict
from mozregui.report import VERDICT_TO_ROW_COLORS


class AskVerdict(QWidget):
    icons_cache = {}

    def __init__(self, parent, delegate):
        QWidget.__init__(self, parent)
        self.delegate = delegate
        self.emitted = False
        self.ui = Ui_AskVerdict()
        self.ui.setupUi(self)
        # build verdict icons
        if not AskVerdict.icons_cache:
            for i in range(self.ui.comboVerdict.count()):
                text = str(self.ui.comboVerdict.itemText(i))
                color = VERDICT_TO_ROW_COLORS.get(text[0])
                pixmap = QPixmap(16, 16)
                pixmap.fill(Qt.transparent)
                if color:
                    painter = QPainter(pixmap)
                    painter.setPen(Qt.black)
                    painter.setBrush(color)
                    painter.drawEllipse(0, 0, 15, 15)
                    painter.end()
                AskVerdict.icons_cache[text] = QIcon(pixmap)
        # set verdict icons
        for i in range(self.ui.comboVerdict.count()):
            text = str(self.ui.comboVerdict.itemText(i))
            self.ui.comboVerdict.setItemIcon(i, AskVerdict.icons_cache[text])

        self.ui.evaluate.clicked.connect(self.on_evaluate_clicked)

    def on_evaluate_clicked(self):
        if not self.emitted:
            # not sure why, but this signal is emitted three times
            # (though the connection is made once, and I click one time)
            # self.emitted is a workaround.
            self.delegate.got_verdict.emit(
                str(self.ui.comboVerdict.currentText())[0]
            )
            self.emitted = True


class ReportItemDelegate(QStyledItemDelegate):
    got_verdict = Signal(str)

    def __init__(self, parent=None, *args):
        QStyledItemDelegate.__init__(self, parent, *args)

    def createEditor(self, parent, option, index):
        if index.model().get_item(index).waiting_evaluation:
            return AskVerdict(parent, self)
        else:
            return QStyledItemDelegate.createEditor(self, parent, option,
                                                    index)

    def paint(self, painter, option, index):
        # if item selected, override default theme
        # Keeps verdict color for cells and use a bold font
        if option.state & QStyle.State_Selected:
            option.state &= ~ QStyle.State_Selected
            option.font.setBold(True)

        QStyledItemDelegate.paint(self, painter, option, index)

        item = index.model().get_item(index)
        if item and item.downloading:
            # Draw progress bar
            progressBarOption = QStyleOptionProgressBarV2()
            progressBarHeight = option.rect.height()/4
            progressBarOption.rect = QRect(
                option.rect.x(),
                option.rect.y() +
                (option.rect.height() - progressBarHeight),
                option.rect.width(),
                progressBarHeight)
            progressBarOption.minimum = 0
            progressBarOption.maximum = 100
            progressBarOption.textAlignment = Qt.AlignCenter

            progressBarOption.progress = item.progress

            QApplication.style().drawControl(
                QStyle.CE_ProgressBar,
                progressBarOption,
                painter)
