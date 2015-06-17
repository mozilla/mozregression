from PyQt4.QtGui import QStyledItemDelegate, QStyleOptionProgressBarV2, \
    QApplication, QStyle
from PyQt4.QtCore import Qt, QRect


class ReportItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, *args):
        QStyledItemDelegate.__init__(self, parent, *args)

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
