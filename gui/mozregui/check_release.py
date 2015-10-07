from PyQt4.QtCore import QObject, QThread, pyqtSlot as Slot, Qt, QUrl
from PyQt4.QtGui import QLabel, QDesktopServices
from mozregression.network import retry_get
from mozregui import __version__
from mozregui.patch_requests import cacert_path


class CheckReleaseThread(QThread):
    GITHUB_LATEST_RELEASE_URL = (
        "https://api.github.com/repos/mozilla/mozregression/releases/latest"
    )

    def __init__(self):
        QThread.__init__(self)
        self.tag_name = None
        self.release_url = None

    def run(self):
        data = retry_get(self.GITHUB_LATEST_RELEASE_URL,
                         verify=cacert_path()).json()
        self.tag_name = data['tag_name']
        self.release_url = data['html_url']


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
        release_name = self.thread.tag_name.replace('gui-', '')
        if release_name == __version__:
            return

        self.label.setText(
            'There is a new release available! Download the new'
            ' <a href="%s">release %s</a>.'
            % (self.thread.release_url, release_name))
        self.mainwindow.ui.status_bar.addWidget(self.label)

    @Slot(str)
    def label_clicked(self, link):
        QDesktopServices.openUrl(QUrl(link))
        self.mainwindow.ui.status_bar.removeWidget(self.label)
