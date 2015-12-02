from PyQt4.QtCore import QDir
from PyQt4.QtGui import QLineEdit, QPushButton, QWidget, QHBoxLayout, \
    QFileDialog, QFileSystemModel, QCompleter, QComboBox, QDateEdit, \
    QStackedWidget

from mozregression.releases import date_of_release, releases
from mozregression.dates import parse_date
from mozregression.errors import DateFormatError


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


class RangeSelection(QWidget):
    """
    Allow to select a date, a build id, a release number or an arbitrary
    changeset.
    """
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        layout = QHBoxLayout(self)
        self._create_widgets()
        layout.addWidget(self.stacked)
        layout.addWidget(self.select_combo)
        self.setLayout(layout)

    def _create_widgets(self):
        self.stacked = QStackedWidget()
        self.datew = QDateEdit()
        self.datew.setDisplayFormat("yyyy-MM-dd")
        self.stacked.addWidget(self.datew)
        self.buildidw = QLineEdit()
        self.stacked.addWidget(self.buildidw)
        self.releasew = QComboBox()
        self.releasew.addItems([str(k) for k in sorted(releases())])
        self.stacked.addWidget(self.releasew)
        self.revw = QLineEdit()
        self.stacked.addWidget(self.revw)

        self.select_combo = QComboBox()
        self.select_combo.addItems(['date', 'buildid', 'release', 'changeset'])
        self.select_combo.activated.connect(self.stacked.setCurrentIndex)

    def get_value(self):
        currentw = self.stacked.currentWidget()
        if currentw == self.datew:
            return self.datew.date().toPyDate()
        elif currentw == self.buildidw:
            buildid = unicode(self.buildidw.text())
            try:
                return parse_date(buildid)
            except DateFormatError:
                raise DateFormatError(buildid, "Not a valid build id: `%s`")
        elif currentw == self.releasew:
            return parse_date(
                date_of_release(str(self.releasew.currentText())))
        elif currentw == self.revw:
            return unicode(self.revw.text())
