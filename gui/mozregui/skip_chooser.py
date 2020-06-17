from PySide2.QtCore import Qt, Signal
from PySide2.QtGui import QBrush
from PySide2.QtWidgets import (
    QDialog,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QMessageBox,
    QToolTip,
)


class BuildItem(QGraphicsRectItem):
    WIDTH = 30

    def __init__(self, future_build_info, x=0, y=0, selectable=True):
        QGraphicsRectItem.__init__(self, x, y, self.WIDTH, self.WIDTH)
        self.future_build_info = future_build_info
        if selectable:
            self.setFlags(self.ItemIsSelectable | self.ItemIsFocusable)
        else:
            self.setFlags(self.ItemIsFocusable)

    def __str__(self):
        return "Build %s" % self.future_build_info.data


class SkipChooserScene(QGraphicsScene):
    COLUMNS = 7
    SPACE = 10

    def __init__(self, build_range):
        QGraphicsScene.__init__(self)
        self.from_range(build_range)

    def from_range(self, build_range):
        self.build_range = build_range
        mid = build_range.mid_point()
        bounds = (0, len(build_range) - 1)
        row = -1
        for i, future in enumerate(build_range.future_build_infos):
            column = i % self.COLUMNS
            if column == 0:
                row += 1
            item = BuildItem(
                future,
                column * BuildItem.WIDTH + self.SPACE * column,
                row * BuildItem.WIDTH + self.SPACE * row,
                selectable=i not in bounds,
            )
            if i == mid:
                item.setBrush(QBrush(Qt.blue))
                self.mid_build = item
            elif i in bounds:
                item.setBrush(QBrush(Qt.lightGray))
            self.addItem(item)


class SkipChooserView(QGraphicsView):
    build_choosen = Signal()

    def __init__(self, parent=None):
        QGraphicsView.__init__(self, parent)
        self.setMouseTracking(True)

    def setScene(self, scene):
        QGraphicsView.setScene(self, scene)
        self.centerOn(scene.mid_build)
        scene.mid_build.setSelected(True)

    def mousePressEvent(self, evt):
        item = self.itemAt(evt.pos())
        # do nothing if we don't click on an item
        if not item:
            return
        # do nothing if we click on a bound
        if not (item.flags() & QGraphicsRectItem.ItemIsSelectable):
            return
        # only one item can be selected at a time, so deselect if any
        for item in self.scene().selectedItems():
            item.setSelected(False)
        QGraphicsView.mousePressEvent(self, evt)

    def mouseMoveEvent(self, evt):
        QGraphicsView.mouseMoveEvent(self, evt)
        # implement a real time tooltip
        item = self.itemAt(evt.pos())
        if item:
            QToolTip.showText(evt.globalPos(), str(item))

    def mouseDoubleClickEvent(self, evt):
        item = self.itemAt(evt.pos())
        # do nothing if we click on a bound
        if item and item.flags() & QGraphicsRectItem.ItemIsSelectable:
            self.build_choosen.emit()


class SkipDialog(QDialog):
    def __init__(self, build_range, parent=None):
        QDialog.__init__(self, parent)
        assert len(build_range) > 3
        from mozregui.ui.skip_dialog import Ui_SkipDialog

        self.ui = Ui_SkipDialog()
        self.ui.setupUi(self)
        self.scene = SkipChooserScene(build_range)
        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.ui.gview.setScene(self.scene)
        self.ui.gview.build_choosen.connect(self.accept)

    def on_selection_changed(self):
        items = self.scene.selectedItems()
        if items:
            self.ui.lbl_status.setText("Selected build to test, %s" % items[0])

    def build_index(self, item):
        return self.scene.build_range.future_build_infos.index(item.future_build_info)

    def choose_next_build(self):
        if self.exec_() == self.Accepted:
            items = self.scene.selectedItems()
            assert len(items) == 1
            return self.build_index(items[0])

    def closeEvent(self, evt):
        if (
            QMessageBox.warning(
                self,
                "Stop the bisection ?",
                "Closing this dialog will end the bisection. Are you sure"
                " you want to end the bisection now ?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            == QMessageBox.Yes
        ):
            evt.accept()
        else:
            evt.ignore()


if __name__ == "__main__":
    from mozregression.build_range import BuildRange, FutureBuildInfo

    class FInfo(FutureBuildInfo):
        def _fetch(self):
            return self.data

    build_range = BuildRange(None, [FInfo(None, i) for i in range(420)])

    from PySide2.QtWidgets import QApplication, QMainWindow

    app = QApplication([])
    win = QMainWindow()

    dlg = SkipDialog(build_range)
