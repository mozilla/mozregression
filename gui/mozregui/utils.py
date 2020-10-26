from PySide2.QtCore import QDir
from PySide2.QtWidgets import (
    QCompleter,
    QFileDialog,
    QFileSystemModel,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from mozregression.dates import parse_date
from mozregression.errors import DateFormatError
from mozregression.releases import date_of_release, releases
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
        self.fsmodel.setFilter(QDir.Drives | QDir.AllDirs | QDir.Hidden | QDir.NoDotAndDotDot)

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
        layout.setContentsMargins(0, 0, 0, 0)
        self.line_edit = FSLineEdit()
        self.button = QPushButton("browse")
        layout.addWidget(self.line_edit)
        layout.addWidget(self.button)
        self.setLayout(layout)

        self.button.clicked.connect(self.browse_dialog)

    def browse_dialog(self):
        path = QFileDialog.getExistingDirectory(self, "Find file")
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
        self.ui.combo_helper.currentIndexChanged.connect(self.ui.stackedWidget.setCurrentIndex)

    def get_value(self):
        currentw = self.ui.stackedWidget.currentWidget()
        if currentw == self.ui.s_date:
            return self.ui.date.date().toPython()
        elif currentw == self.ui.s_release:
            return parse_date(date_of_release(str(self.ui.release.currentText())))
        elif currentw == self.ui.s_buildid:
            buildid = self.ui.buildid.text().strip()
            try:
                return parse_date(buildid)
            except DateFormatError:
                raise DateFormatError(buildid, "Not a valid build id: `%s`")
        elif currentw == self.ui.s_changeset:
            return self.ui.changeset.text().strip()
