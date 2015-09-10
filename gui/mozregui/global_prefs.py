from PyQt4.QtGui import QDialog

from mozregui.ui.global_prefs import Ui_GlobalPrefs
from mozregui import patch_requests

from mozregression.network import set_http_session
from mozregression.config import DEFAULT_CONF_FNAME, get_defaults
from configobj import ConfigObj


def get_prefs():
    """
    Return the global prefs as a dict.
    """
    settings = get_defaults(DEFAULT_CONF_FNAME)
    options = dict()
    options['persist'] = settings['persist']
    options['http_timeout'] = float(settings['http-timeout'])
    return options


def save_prefs(options):
    settings = ConfigObj(DEFAULT_CONF_FNAME)
    settings.update({
        'persist': options['persist'] or '',
        'http-timeout': options['http_timeout'],
    })
    settings.write()


def apply_prefs(options):
    set_http_session(get_defaults={
        "timeout": options['http_timeout'],
        "verify": patch_requests.cacert_path()
    })
    # persist options have to be passed in the bisection, not handled here.


def change_prefs_dialog(parent=None):
    """
    A dialog to change global prefs. This does not apply the prefs.
    """
    dlg = QDialog(parent)
    ui = Ui_GlobalPrefs()
    ui.setupUi(dlg)

    # set default values
    options = get_prefs()
    ui.persist.line_edit.setText(options['persist'] or '')
    ui.http_timeout.setValue(options['http_timeout'])

    if dlg.exec_() == QDialog.Accepted:
        options['persist'] = str(ui.persist.line_edit.text()) or None
        options['http_timeout'] = ui.http_timeout.value()
        save_prefs(options)
