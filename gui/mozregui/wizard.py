import mozinfo
from PyQt4.QtGui import QWizard, QWizardPage, QStringListModel
from PyQt4.QtCore import QString, QDate

from ui.intro import Ui_Intro
from ui.nightlies import Ui_Nightlies
from ui.inbound import Ui_Inbound
from ui.profile import Ui_Profile

from mozregression.fetch_configs import create_config, REGISTRY


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
    TITLE = "Starting a bisection"
    SUBTITLE = "Please choose an application and a type of bisection."
    FIELDS = {'application': 'app_combo', 'bisect_type': 'bisect_combo'}
    ID = 0

    def initializePage(self):
        app_model = QStringListModel(REGISTRY.names())
        self.ui.app_combo.setModel(app_model)
        bisect_model = QStringListModel(['nightlies', 'inbound'])
        self.ui.bisect_combo.setModel(bisect_model)

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

    def nextId(self):
        return ProfilePage.ID


class InboundPage(WizardPage):
    UI_CLASS = Ui_Inbound
    TITLE = "Select the inbound changesets range"
    FIELDS = {"start_changeset": "start_changeset",
              "end_changeset": "end_changeset"}
    ID = 2

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


class BisectionWizard(QWizard):
    def __init__(self, parent=None):
        QWizard.__init__(self, parent)
        self.setWindowTitle("Bisection wizard")

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
        fetch_config = create_config(options['application'],
                                     mozinfo.os, mozinfo.bits)
        return fetch_config, options
