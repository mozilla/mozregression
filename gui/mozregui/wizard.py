import mozinfo
import datetime
from PyQt4.QtGui import QWizard, QWizardPage, QStringListModel, QMessageBox
from PyQt4.QtCore import QString, QDateTime, QTimer, pyqtSlot as Slot

from ui.intro import Ui_Intro
from ui.range_selection import Ui_RangeSelectionPage
from ui.profile import Ui_Profile

from mozregression.fetch_configs import create_config, REGISTRY
from mozregression.launchers import REGISTRY as LAUNCHER_REGISTRY
from mozregression.errors import LauncherNotRunnable, DateFormatError
from mozregression.dates import to_datetime


def resolve_obj_name(obj, name):
    names = name.split('.')
    while names:
        obj = getattr(obj, names.pop(0))
    return obj


class WizardPage(QWizardPage):
    UI_CLASS = None
    TITLE = ''
    SUBTITLE = ''
    FIELDS = {}

    def __init__(self):
        QWizardPage.__init__(self)
        self.setTitle(self.TITLE)
        self.setSubTitle(self.SUBTITLE)
        self.ui = self.UI_CLASS()
        self.ui.setupUi(self)
        for name, widget_name in self.FIELDS.iteritems():
            self.registerField(name, resolve_obj_name(self.ui, widget_name))


class IntroPage(WizardPage):
    UI_CLASS = Ui_Intro
    TITLE = "Basic configuration"
    SUBTITLE = ("Please choose an application and other options related to"
                " the builds you want to test.")
    FIELDS = {'application': 'app_combo', "repository": "repository",
              'bits': 'bits_combo', "build_type": "build_type"}
    ID = 0

    def __init__(self):
        WizardPage.__init__(self)
        self.fetch_config = None
        self.app_model = QStringListModel([a for a in REGISTRY.names()
                                           if not a.startswith('b2g-')])
        self.ui.app_combo.setModel(self.app_model)
        if mozinfo.bits == 64:
            if mozinfo.os == 'mac':
                self.bits_model = QStringListModel(['64'])
                bits_index = 0
            else:
                self.bits_model = QStringListModel(['32', '64'])
                bits_index = 1
        elif mozinfo.bits == 32:
            self.bits_model = QStringListModel(['32'])
            bits_index = 0
        self.ui.bits_combo.setModel(self.bits_model)
        self.ui.bits_combo.setCurrentIndex(bits_index)
        self.build_type_model = QStringListModel()

        self.ui.app_combo.currentIndexChanged.connect(self._set_fetch_config)
        self.ui.bits_combo.currentIndexChanged.connect(self._set_fetch_config)
        self.ui.app_combo.setCurrentIndex(
            self.ui.app_combo.findText("firefox"))

    def _set_fetch_config(self, index):
        app_name = str(self.ui.app_combo.currentText())
        bits = int(self.ui.bits_combo.currentText())

        self.fetch_config = create_config(app_name, mozinfo.os, bits)

        self.build_type_model = QStringListModel(
            [i for i in REGISTRY.get(app_name).BUILD_TYPES])
        self.ui.build_type.setModel(self.build_type_model)

        if not self.fetch_config.available_bits():
            self.ui.bits_combo.hide()
            self.ui.label_4.hide()
        else:
            self.ui.bits_combo.show()
            self.ui.label_4.show()

    def validatePage(self):
        app_name = self.fetch_config.app_name
        launcher_class = LAUNCHER_REGISTRY.get(app_name)
        try:
            launcher_class.check_is_runnable()
            return True
        except LauncherNotRunnable, exc:
            QMessageBox.critical(
                self,
                "%s is not runnable" % app_name,
                str(exc)
            )
            return False

    def nextId(self):
        return ProfilePage.ID


class ProfilePage(WizardPage):
    UI_CLASS = Ui_Profile
    TITLE = "Profile selection"
    SUBTITLE = ("Choose a specific profile. You can choose an existing profile"
                ", or let this blank to use a new one.")
    FIELDS = {"profile": "profile_widget.line_edit",
	          "profile_persistence": "profile_persistence_combo" }
    ID = 1

    def __init__(self):
	WizardPage.__init__(self)
	profile_persistence_options = [ "clone",
					"clone-first",
					"reuse"
				      ]
	self.profile_persistence_model = QStringListModel(profile_persistence_options)
	self.ui.profile_persistence_combo.setModel(self.profile_persistence_model)
	self.ui.profile_persistence_combo.setCurrentIndex(0)

    def get_prefs(self):
        return self.ui.pref_widget.get_prefs()

    def get_addons(self):
        return self.ui.addons_widget.get_addons()

    def get_profile_persistence(self):
        return str(self.ui.profile_persistence_combo.currentText())

    def nextId(self):
        return RangeSelectionPage.ID


class RangeSelectionPage(WizardPage):
    UI_CLASS = Ui_RangeSelectionPage
    TITLE = "Bisection range selection"
    SUBTITLE = ("Select the range to bisect.")
    FIELDS = {'find_fix': 'find_fix'}
    ID = 2

    def __init__(self):
        WizardPage.__init__(self)
        now = QDateTime.currentDateTime()
        self.ui.start.datew.setDateTime(now.addYears(-1))
        self.ui.end.datew.setDateTime(now)
        self.ui.find_fix.stateChanged.connect(self.change_labels)

    @Slot()
    def change_labels(self):
        find_fix = self.ui.find_fix.isChecked()
        if find_fix:
            self.ui.label.setText("Last known bad build")
            self.ui.label_2.setText("First known good build")
        else:
            self.ui.label.setText("Last known good build")
            self.ui.label_2.setText("First known bad build")

    def initializePage(self):
        # set the focus on the first entry
        QTimer.singleShot(0,
                          self.ui.start.stacked.currentWidget().setFocus)

    def get_start(self):
        return self.ui.start.get_value()

    def get_end(self):
        return self.ui.end.get_value()

    def validatePage(self):
        start, end = self.get_start(), self.get_end()
        if isinstance(start, basestring) or isinstance(end, basestring):
            # do not check revisions
            return True
        try:
            start_date = to_datetime(start)
            end_date = to_datetime(end)
        except DateFormatError as exc:
            QMessageBox.critical(self, "Error", unicode(exc))
            return False
        current = datetime.datetime.now()
        if start_date < end_date:
            if end_date <= current:
                return True
            else:
                QMessageBox.critical(
                    self,
                    "Error",
                    "You can't define a date in the future.")
        else:
            QMessageBox.critical(
                self,
                "Error",
                "The first date must be earlier than the second one.")

        return False

    def nextId(self):
        return -1


class BisectionWizard(QWizard):
    def __init__(self, parent=None):
        QWizard.__init__(self, parent)
        self.setWindowTitle("Bisection wizard")
        self.resize(800, 600)

        # associate current text to comboboxes fields instead of current index
        self.setDefaultProperty("QComboBox", "currentText",
                                "currentIndexChanged")

        self.addPage(IntroPage())
        self.addPage(ProfilePage())
        self.addPage(RangeSelectionPage())

    def options(self):
        options = {}
        for page_id in self.pageIds():
            wizard_class = self.page(page_id).__class__
            for fieldname in wizard_class.FIELDS:
                value = self.field(fieldname).toPyObject()
                if isinstance(value, QString):
                    value = unicode(value)
                options[fieldname] = value

        fetch_config = self.page(IntroPage.ID).fetch_config
        fetch_config.set_repo(options['repository'])
        fetch_config.set_build_type(options['build_type'])

        range_page = self.page(RangeSelectionPage.ID)
        options['good'] = range_page.get_start()
        options['bad'] = range_page.get_end()
        if options['find_fix']:
            options['good'], options['bad'] = options['bad'], options['good']

        # get the prefs
        options['preferences'] = self.page(ProfilePage.ID).get_prefs()
        # get the addons
        options['addons'] = self.page(ProfilePage.ID).get_addons()
        # get profile persistence
        options['profile-persistence'] = self.page(ProfilePage.ID).get_profile_persistence()
        # create a profile if required
        launcher_class = LAUNCHER_REGISTRY.get(fetch_config.app_name)
        launcher_class.check_is_runnable()
        if options['profile-persistence'] in ('clone-first', 'reuse'):
            options['profile'] = launcher_class.create_profile(
                    profile=options['profile'],
                    addons=options['addons'],
                    preferences=options['preferences'],
                    clone=options['profile_persistence'] == 'clone-first'
                )

        return fetch_config, options
