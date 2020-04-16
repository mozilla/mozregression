from PySide2.QtCore import QObject, Qt, QThread, QUrl, Slot
from PySide2.QtGui import QDesktopServices
from PySide2.QtWidgets import QLabel

from mozregression import __version__ as mozregression_version
from mozregression.network import retry_get


class CheckReleaseThread(QThread):
    GITHUB_LATEST_RELEASE_URL = "https://api.github.com/repos/mozilla/mozregression/releases/latest"

    def __init__(self):
        QThread.__init__(self)
        self.tag_name = None
        self.release_url = None

    def run(self):
        data = retry_get(self.GITHUB_LATEST_RELEASE_URL).json()
        self.tag_name = data.get("tag_name")
        self.release_url = data.get("html_url")


class CheckRelease(QObject):
    def __init__(self, mainwindow):
        QObject.__init__(self, mainwindow)
        self.mainwindow = mainwindow
        self.thread = CheckReleaseThread()
        self.thread.finished.connect(self.on_release_found)
        lbl = QLabel()
        lbl.setTextFormat(Qt.RichText)
        lbl.setTextInteractionFlags(Qt.TextBrowserInteraction)
        lbl.linkActivated.connect(self.label_clicked)
        self.label = lbl

    def check(self):
        self.thread.start()

    @Slot()
    def on_release_found(self):
        if not self.thread.tag_name or not self.thread.release_url:
            # could not find a release, silently return -- presumably
            # a temporary issue
            return

        release_name = self.thread.tag_name
        if release_name == mozregression_version:
            return

        self.label.setText(
            "There is a new release available! Download the new"
            ' <a href="%s">release %s</a>.' % (self.thread.release_url, release_name)
        )
        self.mainwindow.ui.status_bar.addWidget(self.label)

    @Slot(str)
    def label_clicked(self, link):
        QDesktopServices.openUrl(QUrl(link))
        self.mainwindow.ui.status_bar.removeWidget(self.label)
