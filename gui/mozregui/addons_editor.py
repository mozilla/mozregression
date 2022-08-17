from PySide2.QtCore import QAbstractListModel, QModelIndex, Qt, Slot
from PySide2.QtWidgets import QFileDialog, QWidget

from mozregui.ui.addons_editor import Ui_AddonsEditor


class AddonsModel(QAbstractListModel):
    """
    A Qt model that can edit addons path.
    """

    def __init__(self, parent=None):
        QAbstractListModel.__init__(self, parent)
        self.addons = []

    def rowCount(self, index=QModelIndex()):
        return len(self.addons)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            return self.addons[index.row()]

    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def add_addon(self, addon):
        if addon:
            addons_list_length = len(self.addons)
            self.beginInsertRows(QModelIndex(), addons_list_length, addons_list_length)
            self.addons.append(addon)
            self.endInsertRows()

    def remove_pref(self, row):
        self.beginRemoveRows(QModelIndex(), row, row)
        self.addons.pop(row)
        self.endRemoveRows()


class AddonsWidgetEditor(QWidget):
    """
    A widget to add or remove addons, and buttons to let the user interact.
    """

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.ui = Ui_AddonsEditor()
        self.ui.setupUi(self)

        self.list_model = AddonsModel()
        self.ui.list_view.setModel(self.list_model)

    @Slot()
    def add_addon(self):
        (fileNames, _) = QFileDialog.getOpenFileNames(
            self,
            "Choose one or more addon files",
            filter="addon file (*.xpi)",
        )
        for fileName in fileNames:
            self.list_model.add_addon(fileName)

    @Slot()
    def remove_selected_addons(self):
        selected_rows = sorted(
            set(i.row() for i in self.ui.list_view.selectedIndexes()), reverse=True
        )
        for row in selected_rows:
            self.list_model.remove_pref(row)

    def get_addons(self):
        return self.list_model.addons


if __name__ == "__main__":
    from PySide2.QtWidgets import QApplication

    app = QApplication([])
    view = AddonsWidgetEditor()
    view.show()
    app.exec_()
