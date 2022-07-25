import os
import sys

from PySide2.QtWidgets import QApplication

if sys.platform != "darwin":
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

APP = QApplication([])  # we need an application to create widgets
