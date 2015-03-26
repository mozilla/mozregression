from PyQt4.QtCore import QDir
from PyQt4.QtGui import QLineEdit, QPushButton, QWidget, QHBoxLayout, \
    QFileDialog, QFileSystemModel, QCompleter


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
