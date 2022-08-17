from __future__ import absolute_import

import datetime

import mozinfo
from PySide2.QtCore import SIGNAL, QDate, QStringListModel, Qt, Slot
from PySide2.QtWidgets import QApplication, QCompleter, QMessageBox, QWizard, QWizardPage

from mozregression.branches import get_branches
from mozregression.dates import to_datetime
from mozregression.errors import DateFormatError, LauncherNotRunnable
from mozregression.fetch_configs import REGISTRY, create_config
from mozregression.launchers import REGISTRY as LAUNCHER_REGISTRY

from .ui.build_selection import Ui_BuildSelectionPage
from .ui.intro import Ui_Intro
from .ui.profile import Ui_Profile
from .ui.single_build_selection import Ui_SingleBuildSelectionPage


def resolve_obj_name(obj, name):
    names = name.split(".")
    while names:
        obj = getattr(obj, names.pop(0))
    return obj


class WizardPage(QWizardPage):
    UI_CLASS = None
    TITLE = ""
    SUBTITLE = ""
    FIELDS = {}

    def __init__(self):
        QWizardPage.__init__(self)
        self.setTitle(self.TITLE)
        self.setSubTitle(self.SUBTITLE)
        self.ui = self.UI_CLASS()
        self.ui.setupUi(self)
        for name, widget_name in self.FIELDS.items():
            self.registerField(name, resolve_obj_name(self.ui, widget_name))

    def set_options(self, options):
        """
        Fill the options dict argument with the page information.

        By default, take every field value present in the FIELDS class
        attribute.
        """
        for fieldname in self.FIELDS:
            options[fieldname] = self.field(fieldname)


class IntroPage(WizardPage):
    UI_CLASS = Ui_Intro
    TITLE = "Basic configuration"
    SUBTITLE = "Please choose an application and other options to specify" " what you want to test."
    FIELDS = {
        "application": "app_combo",
        "repository": "repository",
        "bits": "bits_combo",
        "arch": "arch_combo",
        "build_type": "build_type",
        "lang": "lang",
        "url": "url",
    }

    def __init__(self):
        WizardPage.__init__(self)
        self.fetch_config = None
        self.app_model = QStringListModel(
            REGISTRY.names(lambda klass: not getattr(klass, "disable_in_gui", None))
        )
        self.ui.app_combo.setModel(self.app_model)
        if mozinfo.bits == 64:
            if mozinfo.os == "mac":
                self.bits_model = QStringListModel(["64"])
                bits_index = 0
            else:
                self.bits_model = QStringListModel(["32", "64"])
                bits_index = 1
        elif mozinfo.bits == 32:
            self.bits_model = QStringListModel(["32"])
            bits_index = 0
        self.ui.bits_combo.setModel(self.bits_model)
        self.ui.bits_combo.setCurrentIndex(bits_index)
        self.arch_model = QStringListModel()
        self.build_type_model = QStringListModel()

        self.ui.app_combo.currentIndexChanged.connect(self._set_fetch_config)
        self.ui.bits_combo.currentIndexChanged.connect(self._set_fetch_config)
        self.ui.app_combo.setCurrentIndex(self.ui.app_combo.findText("firefox"))

        self.ui.repository.textChanged.connect(self._on_repo_changed)

        completer = QCompleter(sorted(get_branches()), self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.ui.repository.setCompleter(completer)
        QApplication.instance().focusChanged.connect(self._on_focus_changed)

    def _on_repo_changed(self, text):
        enable_release = not text or text == "mozilla-central"
        build_select_page = self.wizard().page(2)
        if type(build_select_page) == SingleBuildSelectionPage:
            build_menus = [build_select_page.ui.build]
        else:
            build_menus = [build_select_page.ui.start, build_select_page.ui.end]
        for menu in build_menus:
            menu.ui.combo_helper.model().item(1).setEnabled(enable_release)
            if menu.ui.combo_helper.currentIndex() == 1:
                menu.ui.combo_helper.setCurrentIndex(0)

    def _on_focus_changed(self, old, new):
        # show the repository completion on focus
        if new == self.ui.repository and not self.ui.repository.text():
            self.ui.repository.completer().complete()

    def _set_fetch_config(self, index):
        app_name = str(self.ui.app_combo.currentText())
        bits = int(self.ui.bits_combo.currentText())

        self.fetch_config = create_config(app_name, mozinfo.os, bits, mozinfo.processor)

        self.arch_model = QStringListModel(self.fetch_config.available_archs())
        self.ui.arch_combo.setModel(self.arch_model)
        if not self.arch_model.stringList():
            self.ui.arch_label.setDisabled(True)
            self.ui.arch_combo.setDisabled(True)
        else:
            self.ui.arch_label.setEnabled(True)
            self.ui.arch_combo.setEnabled(True)

        self.build_type_model = QStringListModel(self.fetch_config.available_build_types())
        self.ui.build_type.setModel(self.build_type_model)

        if not self.fetch_config.available_bits():
            self.ui.bits_combo.setDisabled(True)
            self.ui.label_4.setDisabled(True)
        else:
            self.ui.bits_combo.setEnabled(True)
            self.ui.label_4.setEnabled(True)

        # URL doesn't make sense for Thunderbird
        if app_name == "thunderbird":
            self.ui.url.setDisabled(True)
            self.ui.url_label.setDisabled(True)
        else:
            self.ui.url.setEnabled(True)
            self.ui.url_label.setEnabled(True)

        # lang only makes sense for firefox-l10n, and repo doesn't
        if app_name == "firefox-l10n":
            self.ui.lang.setEnabled(True)
            self.ui.lang_label.setEnabled(True)
            self.ui.repository.setDisabled(True)
            self.ui.repository_label.setDisabled(True)
        else:
            self.ui.lang.setDisabled(True)
            self.ui.lang_label.setDisabled(True)
            self.ui.repository.setEnabled(True)
            self.ui.repository_label.setEnabled(True)

    def validatePage(self):
        app_name = self.fetch_config.app_name
        launcher_class = LAUNCHER_REGISTRY.get(app_name)
        try:
            launcher_class.check_is_runnable()
            return True
        except LauncherNotRunnable as exc:
            QMessageBox.critical(self, "%s is not runnable" % app_name, str(exc))
            return False


class ProfilePage(WizardPage):
    UI_CLASS = Ui_Profile
    TITLE = "Profile selection"
    SUBTITLE = (
        "Choose a specific profile. You can choose an existing profile"
        ", or let this blank to use a new one."
    )
    FIELDS = {
        "profile": "profile_widget.line_edit",
        "profile_persistence": "profile_persistence_combo",
    }

    def __init__(self):
        WizardPage.__init__(self)
        profile_persistence_options = ["clone", "clone-first", "reuse"]
        self.profile_persistence_model = QStringListModel(profile_persistence_options)
        self.ui.profile_persistence_combo.setModel(self.profile_persistence_model)
        self.ui.profile_persistence_combo.setCurrentIndex(0)

    def set_options(self, options):
        WizardPage.set_options(self, options)
        # get the prefs
        options["preferences"] = self.get_prefs()
        # get the addons
        options["addons"] = self.get_addons()
        # get the profile-persistence
        options["profile_persistence"] = self.get_profile_persistence()

    def get_prefs(self):
        return self.ui.pref_widget.get_prefs()

    def get_addons(self):
        return self.ui.addons_widget.get_addons()

    def get_profile_persistence(self):
        return self.ui.profile_persistence_combo.currentText()


class BuildSelectionPage(WizardPage):
    UI_CLASS = Ui_BuildSelectionPage
    TITLE = "Build selection"
    SUBTITLE = "Select the range to bisect."
    FIELDS = {"find_fix": "find_fix"}

    def __init__(self):
        WizardPage.__init__(self)
        now = QDate.currentDate()
        self.ui.start.ui.date.setDate(now.addYears(-1))
        self.ui.end.ui.date.setDate(now)
        self.ui.find_fix.stateChanged.connect(self.change_labels)

    def set_options(self, options):
        WizardPage.set_options(self, options)
        options["good"] = self.get_start()
        options["bad"] = self.get_end()
        if options["find_fix"]:
            options["good"], options["bad"] = options["bad"], options["good"]

    @Slot()
    def change_labels(self):
        find_fix = self.ui.find_fix.isChecked()
        if find_fix:
            self.ui.label.setText("Last known bad build")
            self.ui.label_2.setText("First known good build")
        else:
            self.ui.label.setText("Last known good build")
            self.ui.label_2.setText("First known bad build")

    def get_start(self):
        return self.ui.start.get_value()

    def get_end(self):
        return self.ui.end.get_value()

    def validatePage(self):
        start, end = self.get_start(), self.get_end()
        if isinstance(start, str) or isinstance(end, str):
            # do not check revisions
            return True
        try:
            start_date = to_datetime(start)
            end_date = to_datetime(end)
        except DateFormatError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return False
        current = datetime.datetime.now()
        if start_date < end_date:
            if end_date <= current:
                return True
            else:
                QMessageBox.critical(self, "Error", "You can't define a date in the future.")
        else:
            QMessageBox.critical(
                self, "Error", "The first date must be earlier than the second one."
            )

        return False


class Wizard(QWizard):
    def __init__(self, title, class_pages, parent=None):
        QWizard.__init__(self, parent)
        self.setWindowTitle(title)
        self.resize(800, 600)

        # associate current text to comboboxes fields instead of current index
        self.setDefaultProperty("QComboBox", "currentText", SIGNAL("currentIndexChanged(QString)"))

        for klass in class_pages:
            self.addPage(klass())

    def options(self):
        options = {}
        for page_id in self.pageIds():
            self.page(page_id).set_options(options)

        fetch_config = self.page(self.pageIds()[0]).fetch_config
        fetch_config.set_repo(options["repository"])
        if options["arch"]:
            fetch_config.set_arch(options["arch"])
        fetch_config.set_build_type(options["build_type"])

        # create a profile if required
        launcher_class = LAUNCHER_REGISTRY.get(fetch_config.app_name)
        if options["profile_persistence"] in ("clone-first", "reuse"):
            options["profile"] = launcher_class.create_profile(
                profile=options["profile"],
                addons=options["addons"],
                preferences=options["preferences"],
                clone=options["profile_persistence"] == "clone-first",
            )

        return fetch_config, options


class BisectionWizard(Wizard):
    def __init__(self, parent=None):
        Wizard.__init__(
            self,
            "Bisection wizard",
            (IntroPage, ProfilePage, BuildSelectionPage),
            parent=parent,
        )


class SingleBuildSelectionPage(WizardPage):
    UI_CLASS = Ui_SingleBuildSelectionPage
    TITLE = "Build selection"
    SUBTITLE = "Select the build you want to run."

    def __init__(self):
        WizardPage.__init__(self)
        now = QDate.currentDate()
        self.ui.build.ui.date.setDate(now.addDays(-3))

    def set_options(self, options):
        WizardPage.set_options(self, options)
        options["launch"] = self.ui.build.get_value()


class SingleRunWizard(Wizard):
    def __init__(self, parent=None):
        Wizard.__init__(
            self,
            "Single run wizard",
            (IntroPage, ProfilePage, SingleBuildSelectionPage),
            parent=parent,
        )
