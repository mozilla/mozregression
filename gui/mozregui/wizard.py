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


def changelabel(self, checkstatus):
    if checkstatus is True:
        self.ui.label.setText("Last known bad date")
        self.ui.label_2.setText("First known good date")
    else:
        self.ui.label.setText("Last known good date")
        self.ui.label_2.setText("First known bad date")


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
    TITLE = "Starting a bisection"
    SUBTITLE = "Please choose an application and a type of bisection."
    FIELDS = {'application': 'app_combo', 'bisect_type': 'bisect_combo',
              'find_fix': 'find_fix'}
    ID = 0

    def __init__(self):
        WizardPage.__init__(self)
        self.fetch_config = None
        self.app_model = QStringListModel(REGISTRY.names())
        self.ui.app_combo.setModel(self.app_model)
        self.bisect_model = QStringListModel()
        self.ui.bisect_combo.setModel(self.bisect_model)

        self.ui.app_combo.currentIndexChanged.connect(self._set_fetch_config)
        self._set_fetch_config(0)

    def _set_fetch_config(self, index):
        # limit bisection type given the application
        old_bisect_index = self.ui.bisect_combo.currentIndex()
        self.fetch_config = create_config(
            str(self.ui.app_combo.itemText(index)), mozinfo.os, mozinfo.bits)
        bisect_types = ['nightlies']
        if self.fetch_config.is_inbound():
            bisect_types.append('inbound')
        self.bisect_model.setStringList(bisect_types)
        bisect_index = 0
        if old_bisect_index == 1 and len(bisect_types) == 2:
            bisect_index = 1
        self.ui.bisect_combo.setCurrentIndex(bisect_index)

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


class NightliesPage(WizardPage):
    UI_CLASS = Ui_Nightlies
    TITLE = "Select the nightlies date range"
    FIELDS = {"start_date": "start_date", "end_date": "end_date"}
    ID = 1

    def __init__(self):
        WizardPage.__init__(self)
        now = QDateTime.currentDateTime()
        self.ui.start_date.setDateTime(now.addYears(-1))
        self.ui.end_date.setDateTime(now)

    def initializePage(self):
        checkstatus = self.wizard().field("find_fix").toBool()
        changelabel(self, checkstatus)

    def validatePage(self):
        good_date = self.ui.start_date.date()
        bad_date = self.ui.end_date.date()
        current = QDateTime.currentDateTime().date()
        if good_date < bad_date:
            if bad_date <= current:
                return True
            else:
                QMessageBox.critical(
                    self,
                    "Error",
                    "Date you entered is larger than now,please try it again.")
                return False
        else:
            QMessageBox.critical(
                self,
                "Error",
                "Dates in good date field can't larger than bad date,\
                please try it again.")
            return False

    def nextId(self):
        return ProfilePage.ID


class InboundPage(WizardPage):
    UI_CLASS = Ui_Inbound
    TITLE = "Select the inbound changesets range"
    FIELDS = {"start_changeset": "start_changeset",
              "end_changeset": "end_changeset"}
    ID = 2

    def initializePage(self):
        checkstatus = self.wizard().field("find_fix").toBool()
        changelabel(self, checkstatus)

    def nextId(self):
        return ProfilePage.ID


class ProfilePage(WizardPage):
    UI_CLASS = Ui_Profile
    TITLE = "Choose a specific profile"
    SUBTITLE = ("You can choose an existing profile, or let this blank to"
                " use a new one.")
    FIELDS = {"profile": "profile_widget.line_edit"}
    ID = 3

    def nextId(self):
        return -1

    def get_prefs(self):
        return self.ui.pref_widget.get_prefs()


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
                    value = str(value)
                elif isinstance(value, QDate):
                    value = value.toPyDate()
                options[fieldname] = value

        if options['bisect_type'] == 'nightlies':
            if options['find_fix'] is False:
                options['good_date'] = options.pop('start_date')
                options['bad_date'] = options.pop('end_date')
            else:
                options['good_date'] = options.pop('end_date')
                options['bad_date'] = options.pop('start_date')

        if options['bisect_type'] == 'inbound':
            if options['find_fix'] is False:
                options['good_changeset'] = options.pop('start_changeset')
                options['bad_changeset'] = options.pop('end_changeset')
            else:
                options['good_changeset'] = options.pop('end_changeset')
                options['bad_changeset'] = options.pop('start_changeset')

        # get the prefs
        options['preferences'] = self.page(ProfilePage.ID).get_prefs()

        fetch_config = self.page(IntroPage.ID).fetch_config
        return fetch_config, options
