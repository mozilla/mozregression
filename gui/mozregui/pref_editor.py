from PyQt4.QtCore import QAbstractTableModel, QModelIndex, Qt, \
    pyqtSlot as Slot
from PyQt4.QtGui import QFileDialog, QWidget
from mozprofile.prefs import Preferences

from mozregui.ui.pref_editor import Ui_PrefEditor


class PreferencesModel(QAbstractTableModel):
    """
    A Qt model that can edit preferences.
    """
    def __init__(self):
        QAbstractTableModel.__init__(self)
        self.prefs = []

    def rowCount(self, index=QModelIndex()):
        return len(self.prefs)

    def columnCount(self, index=QModelIndex()):
        return 2

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return ('name', 'value')[section]

    def data(self, index, role=Qt.DisplayRole):
        if role in (Qt.DisplayRole, Qt.EditRole):
            name, value = self.prefs[index.row()]
            if index.column() == 0:
                return name
            else:
                if isinstance(value, basestring):
                    return '"' + value + '"'
                else:
                    return value

    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled

    def setData(self, index, new_value, role=Qt.EditRole):
        new_value = unicode(new_value.toString())
        name, value = self.prefs[index.row()]
        if index.column() == 0:
            # change pref name
            name = new_value
        else:
            # change pref value
            value = Preferences.cast(new_value)
        self.prefs[index.row()] = (name, value)
        return True

    def add_empty_pref(self):
        nb_prefs = len(self.prefs)
        self.beginInsertRows(QModelIndex(), nb_prefs, nb_prefs)
        self.prefs.append(('', ''))
        self.endInsertRows()

    def add_prefs_from_file(self, fname):
        prefs = Preferences.read(fname)
        if prefs:
            nb_prefs = len(self.prefs)
            self.beginInsertRows(QModelIndex(), nb_prefs,
                                 nb_prefs + len(prefs) - 1)
            self.prefs.extend(prefs.items())
            self.endInsertRows()

    def remove_pref(self, row):
        self.beginRemoveRows(QModelIndex(), row, row)
        self.prefs.pop(row)
        self.endRemoveRows()


class PreferencesWidgetEditor(QWidget):
    """
    A widget to edit preferences, using PreferencesModel in a table view
    and buttons to let the user interact.
    """
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.ui = Ui_PrefEditor()
        self.ui.setupUi(self)

        self.pref_model = PreferencesModel()
        self.ui.pref_view.setModel(self.pref_model)

    @Slot()
    def add_pref(self):
        self.pref_model.add_empty_pref()
        # enter in edit mode for the pref name
        index = self.pref_model.index(self.pref_model.rowCount() - 1, 0)
        self.ui.pref_view.edit(index)

    @Slot()
    def add_prefs_from_file(self):
        fname = QFileDialog.getOpenFileName(
            self,
            "Choose a preference file",
            filter="pref file (*.json *.ini)",
        )
        if fname:
            self.pref_model.add_prefs_from_file(unicode(fname))

    @Slot()
    def remove_selected_prefs(self):
        selected_rows = sorted(
            set(i.row() for i in self.ui.pref_view.selectedIndexes()),
            reverse=True
        )
        for row in selected_rows:
            self.pref_model.remove_pref(row)

    def get_prefs(self):
        return self.pref_model.prefs[:]


if __name__ == '__main__':
    from PyQt4.QtGui import QApplication

    app = QApplication([])
    view = PreferencesWidgetEditor()
    view.show()
    app.exec_()
