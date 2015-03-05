# Import PySide classes
import sys
from PySide.QtGui import QApplication, QMainWindow
from PySide.QtCore import Slot

from ui.mainwindow import Ui_MainWindow
from wizard import BisectionWizard


class MainWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

    @Slot()
    def start_bisection_wizard(self):
        wizard = BisectionWizard(self)
        if wizard.exec_() == wizard.Accepted:
            print wizard.field_options()


if __name__ == '__main__':
    # Create a Qt application
    app = QApplication(sys.argv)
    # Create the main window and show it
    win = MainWindow()
    win.show()
    win.start_bisection_wizard()
    # Enter Qt application main loop
    sys.exit(app.exec_())
