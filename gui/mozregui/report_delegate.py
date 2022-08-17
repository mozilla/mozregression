from PySide2.QtCore import QRect, Qt, Signal
from PySide2.QtGui import QIcon, QPainter, QPixmap
from PySide2.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionProgressBar,
    QWidget,
)

from mozregui.report import VERDICT_TO_ROW_COLORS
from mozregui.ui.ask_verdict import Ui_AskVerdict

VERDICTS = ("good", "bad", "skip", "retry", "other...")


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
            for text in VERDICTS:
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

        # set combo verdict
        for text in ("other...", "skip", "retry"):
            self.ui.comboVerdict.addItem(AskVerdict.icons_cache[text], text)
        model = self.ui.comboVerdict.model()
        model.itemFromIndex(model.index(0, 0)).setSelectable(False)

        self.ui.comboVerdict.activated.connect(self.on_dropdown_item_activated)

        self.ui.goodVerdict.clicked.connect(self.on_good_bad_button_clicked)
        self.ui.goodVerdict.setIcon(AskVerdict.icons_cache["good"])

        self.ui.badVerdict.clicked.connect(self.on_good_bad_button_clicked)
        self.ui.badVerdict.setIcon(AskVerdict.icons_cache["bad"])

    def on_dropdown_item_activated(self):
        self.delegate.got_verdict.emit(str(self.ui.comboVerdict.currentText())[0].lower())
        self.emitted = True

    def on_good_bad_button_clicked(self):
        self.delegate.got_verdict.emit(str(self.sender().text())[0].lower())
        self.emitted = True


class ReportItemDelegate(QStyledItemDelegate):
    got_verdict = Signal(str)

    def __init__(self, parent=None, *args):
        QStyledItemDelegate.__init__(self, parent, *args)

    def createEditor(self, parent, option, index):
        if index.model().get_item(index).waiting_evaluation:
            return AskVerdict(parent, self)
        else:
            return QStyledItemDelegate.createEditor(self, parent, option, index)

    def paint(self, painter, option, index):
        # if item selected, override default theme
        # Keeps verdict color for cells and use a bold font
        if option.state & QStyle.State_Selected:
            option.state &= ~QStyle.State_Selected
            option.font.setBold(True)

        QStyledItemDelegate.paint(self, painter, option, index)

        item = index.model().get_item(index)
        if item and item.downloading:
            # Draw progress bar
            progressBarOption = QStyleOptionProgressBar()
            progressBarHeight = option.rect.height() / 4
            progressBarOption.rect = QRect(
                option.rect.x(),
                option.rect.y() + (option.rect.height() - progressBarHeight),
                option.rect.width(),
                progressBarHeight,
            )
            progressBarOption.minimum = 0
            progressBarOption.maximum = 100
            progressBarOption.textAlignment = Qt.AlignCenter

            progressBarOption.progress = item.progress

            QApplication.style().drawControl(QStyle.CE_ProgressBar, progressBarOption, painter)
