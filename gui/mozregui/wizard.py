import mozinfo
from PyQt4.QtGui import QWizard, QWizardPage, QStringListModel, QMessageBox
from PyQt4.QtCore import QString, QDate, QDateTime

from ui.intro import Ui_Intro
from ui.nightlies import Ui_Nightlies
from ui.inbound import Ui_Inbound
from ui.profile import Ui_Profile

from mozregression.fetch_configs import create_config, REGISTRY
from mozregression.launchers import REGISTRY as LAUNCHER_REGISTRY
from mozregression.errors import LauncherNotRunnable


def get_all_subclasses(cls):
    all_subclasses = []

    for subclass in cls.__subclasses__():
        all_subclasses.append(subclass)
        all_subclasses.extend(get_all_subclasses(subclass))

    return all_subclasses


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
    TITLE = "Bisection start"
    SUBTITLE = ("Please choose an application, a type of bisection"
                " and the number of bits for the application.")
    FIELDS = {'application': 'app_combo', 'bisect_type': 'bisect_combo',
              'find_fix': 'find_fix', 'bits': 'bits_combo'}
    ID = 0

    def __init__(self):
        WizardPage.__init__(self)
        self.fetch_config = None
        self.app_model = QStringListModel([a for a in REGISTRY.names()
                                           if not a.startswith('b2g-')])
        self.ui.app_combo.setModel(self.app_model)
        self.bisect_model = QStringListModel()
        self.ui.bisect_combo.setModel(self.bisect_model)
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

        self.ui.app_combo.currentIndexChanged.connect(self._set_fetch_config)
        self.ui.bits_combo.currentIndexChanged.connect(self._set_fetch_config)
        self.ui.app_combo.setCurrentIndex(
            self.ui.app_combo.findText("firefox"))

    def _set_fetch_config(self, index):
        # limit bisection type given the application
        bits = int(self.ui.bits_combo.currentText())
        old_bisect_index = self.ui.bisect_combo.currentIndex()
        self.fetch_config = create_config(
            str(self.ui.app_combo.currentText()),
            mozinfo.os, bits)
        bisect_types = ['nightlies']
        if self.fetch_config.is_inbound():
            bisect_types.append('inbound')
        self.bisect_model.setStringList(bisect_types)
        bisect_index = 0
        if old_bisect_index == 1 and len(bisect_types) == 2:
            bisect_index = 1
        self.ui.bisect_combo.setCurrentIndex(bisect_index)
        available_bits = self.fetch_config.available_bits()
        if not available_bits:
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
        if self.ui.bisect_combo.currentText() == 'nightlies':
            return NightliesPage.ID
        else:
            return InboundPage.ID


class WizardSelectionRangePage(WizardPage):
    RANGE_TYPE = 'date'

    def changelabel(self, checkstatus):
        if checkstatus is True:
            self.ui.label.setText("Last known bad %s" % self.RANGE_TYPE)
            self.ui.label_2.setText("First known good %s" % self.RANGE_TYPE)
        else:
            self.ui.label.setText("Last known good %s" % self.RANGE_TYPE)
            self.ui.label_2.setText("First known bad %s" % self.RANGE_TYPE)

    def initializePage(self):
        checkstatus = self.wizard().field("find_fix").toBool()
        self.changelabel(checkstatus)


class NightliesPage(WizardSelectionRangePage):
    UI_CLASS = Ui_Nightlies
    TITLE = "Date range selection"
    SUBTITLE = ("Select the nightlies date range.")
    FIELDS = {"start_date": "start_date", "end_date": "end_date",
              "repository": "repository"}
    ID = 1

    def __init__(self):
        WizardPage.__init__(self)
        now = QDateTime.currentDateTime()
        self.ui.start_date.setDateTime(now.addYears(-1))
        self.ui.end_date.setDateTime(now)

    def validatePage(self):
        start_date = self.ui.start_date.date()
        end_date = self.ui.end_date.date()
        current = QDateTime.currentDateTime().date()
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
        return ProfilePage.ID


class InboundPage(WizardSelectionRangePage):
    RANGE_TYPE = "revision"
    UI_CLASS = Ui_Inbound
    TITLE = "Changesets range selection"
    SUBTITLE = "Select the inbound changesets range."
    FIELDS = {"start_changeset": "start_changeset",
              "end_changeset": "end_changeset",
              "inbound_branch": "inbound_branch"}
    ID = 2

    def nextId(self):
        return ProfilePage.ID


class ProfilePage(WizardPage):
    UI_CLASS = Ui_Profile
    TITLE = "Profile selection"
    SUBTITLE = ("Choose a specific profile. You can choose an existing profile"
                ", or let this blank to use a new one.")
    FIELDS = {"profile": "profile_widget.line_edit"}
    ID = 3

    def nextId(self):
        return -1

    def get_prefs(self):
        return self.ui.pref_widget.get_prefs()

    def get_addons(self):
        return self.ui.addons_widget.get_addons()


class BisectionWizard(QWizard):
    def __init__(self, parent=None):
        QWizard.__init__(self, parent)
        self.setWindowTitle("Bisection wizard")
        self.resize(800, 600)

        # associate current text to comboboxes fields instead of current index
        self.setDefaultProperty("QComboBox", "currentText",
                                "currentIndexChanged")
        # store QDate instead of QDateTime
        self.setDefaultProperty("QDateEdit", "date", "dateChanged")

        self.addPage(IntroPage())
        self.addPage(NightliesPage())
        self.addPage(InboundPage())
        self.addPage(ProfilePage())

    def options(self):
        options = {}
        for wizard_class in get_all_subclasses(WizardPage):
            for fieldname in wizard_class.FIELDS:
                value = self.field(fieldname).toPyObject()
                if isinstance(value, QString):
                    value = unicode(value)
                elif isinstance(value, QDate):
                    value = value.toPyDate()
                options[fieldname] = value
        fetch_config = self.page(IntroPage.ID).fetch_config
        if options['bisect_type'] == 'nightlies':
            kind = "date"
            fetch_config.set_nightly_repo(options['repository'])
        else:
            kind = "changeset"
            fetch_config.set_inbound_branch(options['inbound_branch'])
        if options['find_fix'] is False:
            options['good_' + kind] = options.pop('start_' + kind)
            options['bad_' + kind] = options.pop('end_' + kind)
        else:
            options['good_' + kind] = options.pop('end_' + kind)
            options['bad_' + kind] = options.pop('start_' + kind)

        # get the prefs
        options['preferences'] = self.page(ProfilePage.ID).get_prefs()
        # get the addons
        options['addons'] = self.page(ProfilePage.ID).get_addons()

        return fetch_config, options
