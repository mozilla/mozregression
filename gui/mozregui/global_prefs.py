import os

from configobj import ConfigObj
from glean import Glean
from PySide2.QtWidgets import QDialog

from mozregression.config import ARCHIVE_BASE_URL, DEFAULT_CONF_FNAME, get_config
from mozregression.network import set_http_session
from mozregui.ui.global_prefs import Ui_GlobalPrefs


def get_prefs():
    """
    Return the global prefs as a dict.
    """
    settings = get_config(DEFAULT_CONF_FNAME)
    options = dict()
    options["persist"] = settings["persist"]
    options["http_timeout"] = float(settings["http-timeout"])
    options["persist_size_limit"] = float(settings["persist-size-limit"])
    options["background_downloads"] = (
        False if settings.get("background_downloads") == "no" else True
    )
    options["approx_policy"] = settings["approx-policy"] == "auto"
    options["archive_base_url"] = settings["archive-base-url"]
    options["cmdargs"] = settings["cmdargs"]
    options["enable_telemetry"] = not settings.get("enable-telemetry") in ["no", "0", "false"]

    return options


def save_prefs(options):
    conf_dir = os.path.dirname(DEFAULT_CONF_FNAME)
    if not os.path.isdir(conf_dir):
        os.makedirs(conf_dir)

    settings = ConfigObj(DEFAULT_CONF_FNAME)
    settings.update(
        {
            "persist": options["persist"] or "",
            "http-timeout": options["http_timeout"],
            "persist-size-limit": options["persist_size_limit"],
            "background_downloads": "yes" if options["background_downloads"] else "no",
            "approx-policy": "auto" if options["approx_policy"] else "none",
            "enable-telemetry": "yes" if options["enable_telemetry"] else "no",
        }
    )
    # only save base url in the file if it differs from the default.
    if options["archive_base_url"] and options["archive_base_url"] != ARCHIVE_BASE_URL:
        settings["archive-base-url"] = options["archive_base_url"]
    elif "archive-base-url" in settings:
        del settings["archive-base-url"]
    # likewise only save args if it has a value
    if "cmdargs" in settings and not settings["cmdargs"]:
        del settings["cmdargs"]

    settings.write()


def set_default_prefs():
    """Set the default prefs for a first launch of the application."""
    if not os.path.isfile(DEFAULT_CONF_FNAME):
        options = get_prefs()
        options["persist"] = os.path.join(os.path.dirname(DEFAULT_CONF_FNAME), "persist")
        options["persist_size_limit"] = 2.0
        save_prefs(options)


def apply_prefs(options):
    set_http_session(get_defaults={"timeout": options["http_timeout"]})
    # persist options have to be passed in the bisection, not handled here.


class ChangePrefsDialog(QDialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.ui = Ui_GlobalPrefs()
        self.ui.setupUi(self)

        # set default values
        options = get_prefs()
        self.ui.persist.line_edit.setText(options["persist"] or "")
        self.ui.http_timeout.setValue(options["http_timeout"])
        self.ui.persist_size_limit.setValue(options["persist_size_limit"])
        self.ui.bg_downloads.setChecked(options["background_downloads"])
        self.ui.approx.setChecked(options["approx_policy"])
        self.ui.archive_base_url.setText(options["archive_base_url"])
        self.ui.advanced_options.setText("Show Advanced Options")
        self.ui.enable_telemetry.setChecked(options["enable_telemetry"])
        self.toggle_visibility(False)
        self.ui.advanced_options.clicked.connect(self.toggle_adv_options)

    def toggle_adv_options(self):
        if self.ui.advanced_options.text() == "Show Advanced Options":
            self.ui.advanced_options.setText("Hide Advanced Options")
            self.toggle_visibility(True)
        else:
            self.ui.advanced_options.setText("Show Advanced Options")
            self.toggle_visibility(False)

    def toggle_visibility(self, visible):
        self.ui.http_timeout.setVisible(visible)
        self.ui.label_3.setVisible(visible)
        self.ui.bg_downloads.setVisible(visible)
        self.ui.label_2.setVisible(visible)
        self.ui.archive_base_url.setVisible(visible)
        self.ui.label_5.setVisible(visible)
        self.ui.enable_telemetry.setVisible(visible)
        self.ui.telemetryLabel.setVisible(visible)

    def save_prefs(self):
        options = get_prefs()
        ui = self.ui

        options["persist"] = str(ui.persist.line_edit.text()) or None
        options["http_timeout"] = ui.http_timeout.value()
        options["persist_size_limit"] = ui.persist_size_limit.value()
        options["background_downloads"] = ui.bg_downloads.isChecked()
        options["approx_policy"] = ui.approx.isChecked()
        options["archive_base_url"] = str(ui.archive_base_url.text())
        options["enable_telemetry"] = ui.enable_telemetry.isChecked()

        # if telemetry went from enabled to disabled, we will send a deletion
        # ping
        Glean.set_upload_enabled(options["enable_telemetry"])

        save_prefs(options)


def change_prefs_dialog(parent=None):
    """
    A dialog to change global prefs. This does not apply the prefs.
    """
    dlg = ChangePrefsDialog(parent)
    if dlg.exec_() == QDialog.Accepted:
        dlg.save_prefs()
