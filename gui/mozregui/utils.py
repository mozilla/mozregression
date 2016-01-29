from PyQt4.QtCore import QDir
from PyQt4.QtGui import QLineEdit, QPushButton, QWidget, QHBoxLayout, \
    QFileDialog, QFileSystemModel, QCompleter

from mozregression.releases import date_of_release, releases
from mozregression.dates import parse_date
from mozregression.errors import DateFormatError
from mozregui.ui.build_selection_helper import Ui_BuildSelectionHelper


class FSLineEdit(QLineEdit):
    """
    A line edit with auto completion for file system folders.
    """
    def __init__(self, parent=None):
        QLineEdit.__init__(self, parent)
        self.fsmodel = QFileSystemModel()
        self.fsmodel.setRootPath("")
        self.completer = QCompleter()
        self.completer.setModel(self.fsmodel)
        self.setCompleter(self.completer)
        self.fsmodel.setFilter(QDir.Drives | QDir.AllDirs | QDir.Hidden |
                               QDir.NoDotAndDotDot)

    def setPath(self, path):
        self.setText(path)
        self.fsmodel.setRootPath(path)


class DirectorySelectWidget(QWidget):
    """
    A FSLineEdit with a "browse" button on the right. Allow to select a
    directory.
    """
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        layout = QHBoxLayout(self)
        self.line_edit = FSLineEdit()
        self.button = QPushButton("browse")
        layout.addWidget(self.line_edit)
        layout.addWidget(self.button)
        self.setLayout(layout)

        self.button.clicked.connect(self.browse_dialog)

    def browse_dialog(self):
        path = QFileDialog.getExistingDirectory(
            self, "Find file"
        )
        if path:
            self.line_edit.setPath(path)


class BuildSelection(QWidget):
    """
    Allow to select a date, a build id, a release number or an arbitrary
    changeset.
    """
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.ui = Ui_BuildSelectionHelper()
        self.ui.setupUi(self)
        self.ui.release.addItems([str(k) for k in sorted(releases())])
        self.ui.combo_helper.activated.connect(
            self.ui.stackedWidget.setCurrentIndex)

    def get_value(self):
        currentw = self.ui.stackedWidget.currentWidget()
        if currentw == self.ui.calendar:
            return self.ui.date.selectedDate().toPyDate()
        elif currentw == self.ui.combo:
            return parse_date(
                date_of_release(str(self.ui.release.currentText())))
        elif currentw == self.ui.lineEdit1:
            buildid = unicode(self.ui.buildid.text())
            try:
                return parse_date(buildid)
            except DateFormatError:
                raise DateFormatError(buildid, "Not a valid build id: `%s`")
        elif currentw == self.ui.lineEdit2:
            return unicode(self.ui.changeset.text())
