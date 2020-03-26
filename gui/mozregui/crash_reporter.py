import platform
import sys
import traceback

from PySide2.QtCore import QObject, Qt, Signal, Slot
from PySide2.QtWidgets import QDialog

import mozregression

from .ui.crash_reporter import Ui_CrashDialog


class CrashDialog(QDialog):
    ERR_TEMPLATE = """\
platform: %(platform)s
python: %(python)s (%(arch)s)
mozregression: %(mozregression)s
message: %(message)s
traceback: %(traceback)s
"""

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.ui = Ui_CrashDialog()
        self.ui.setupUi(self)

    def set_exception(self, type, value, tb):
        frozen = " FROZEN" if getattr(sys, "frozen", False) else ""
        self.ui.information.setPlainText(
            self.ERR_TEMPLATE
            % dict(
                mozregression=mozregression.__version__,
                message="%s: %s" % (type.__name__, value),
                traceback="".join(traceback.format_tb(tb)) if tb else "NONE",
                platform=platform.platform(),
                python=platform.python_version() + frozen,
                arch=platform.architecture()[0],
            )
        )


class CrashReporter(QObject):
    DIALOG_CLASS = CrashDialog
    got_exception = Signal(tuple)

    def __init__(self, app):
        QObject.__init__(self, app)
        self._sys_except_hook = sys.excepthook
        self.app = app
        self.allow_dialog = True
        self.current_dialog = None
        self.got_exception.connect(self.display_dialog, Qt.QueuedConnection)

    def install(self):
        sys.excepthook = self.on_exception

    def uninstall(self):
        sys.excepthook = self._sys_except_hook

    def on_exception(self, *args):
        self._sys_except_hook(*args)
        self.got_exception.emit(args)

    @Slot(int)
    def on_prevent_dialog_checked(self, state):
        self.allow_dialog = state != Qt.Checked

    @Slot(tuple)
    def display_dialog(self, err):
        if not self.allow_dialog or self.current_dialog:
            return
        self.current_dialog = self.DIALOG_CLASS(self.app.focusWidget())
        self.current_dialog.ui.check_hide_dialog.stateChanged.connect(
            self.on_prevent_dialog_checked
        )
        self.current_dialog.set_exception(*err)
        self.current_dialog.exec_()
        self.current_dialog = None
