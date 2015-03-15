import mozinfo
from PySide.QtGui import QWidget, QStringListModel

from mozregression.fetch_configs import REGISTRY, create_config

from mozregui.ui.bisect_options import Ui_Form


class BisectOptions(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._fetch_fonfig = None

        self.ui = Ui_Form()
        self.ui.setupUi(self)

        self.ui.bisect_combo.setModel(QStringListModel())

        app_model = QStringListModel(REGISTRY.names())
        self.ui.app_combo.setModel(app_model)

        self.ui.app_combo.activated.connect(self.on_app_choosen)
        self.on_app_choosen(self.ui.app_combo.currentIndex())

    def on_app_choosen(self, index):
        self._fetch_config = create_config(self.ui.app_combo.currentText(),
                                           mozinfo.os,
                                           mozinfo.bits)
        apps = []
        if self._fetch_config.is_nightly():
            apps.append('nightlies')
        if self._fetch_config.is_inbound():
            apps.append('inbounds')

        new_index = self.ui.bisect_combo.currentIndex()
        self.ui.bisect_combo.model().setStringList(apps)
        if new_index == -1 or (new_index == 1 and len(apps) < 2):
            new_index = 0
        self.ui.bisect_combo.setCurrentIndex(new_index)

    def fetch_config(self):
        return self._fetch_config

    def bisect_options(self):
        return {
            'application': self.ui.app_combo.currentText(),
            'bisect_type': self.ui.bisect_combo.currentText(),
            "start_date": self.ui.start_date.date().toPython(),
            "end_date": self.ui.end_date.date().toPython(),
            "start_changeset": self.ui.start_changeset.text(),
            "end_changeset": self.ui.end_changeset.text(),
        }
