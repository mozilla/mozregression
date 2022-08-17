import os
import tempfile

import pytest
from mock import Mock
from PySide2.QtWidgets import QDialog

from mozregui import global_prefs


@pytest.yield_fixture
def write_default_conf():
    default_file = global_prefs.DEFAULT_CONF_FNAME
    conf_file = tempfile.NamedTemporaryFile(delete=False)
    global_prefs.DEFAULT_CONF_FNAME = conf_file.name
    conf_file.close()

    def write_conf(text):
        with open(conf_file.name, "w") as f:
            f.write(text)

    yield write_conf

    global_prefs.DEFAULT_CONF_FNAME = default_file
    os.unlink(conf_file.name)


def test_change_prefs_dialog(write_default_conf, qtbot):
    write_default_conf(
        """
http-timeout = 32.1
persist-size-limit = 2.5
"""
    )

    pref_dialog = global_prefs.ChangePrefsDialog()
    qtbot.add_widget(pref_dialog)
    pref_dialog.show()
    qtbot.waitForWindowShown(pref_dialog)

    # defaults are set
    assert str(pref_dialog.ui.persist.line_edit.text()) == ""
    assert pref_dialog.ui.http_timeout.value() == 32.1
    assert pref_dialog.ui.persist_size_limit.value() == 2.5

    # now let's change some values
    qtbot.keyClicks(pref_dialog.ui.persist.line_edit, "/path/to")

    # then save the prefs
    pref_dialog.save_prefs()

    # check they have been registered
    assert global_prefs.get_prefs().get("persist") == "/path/to"


@pytest.mark.parametrize("dlg_result,saved", [(QDialog.Accepted, True), (QDialog.Rejected, False)])
def test_change_prefs_dialog_saves_prefs(dlg_result, saved, mocker):
    Dlg = mocker.patch("mozregui.global_prefs.ChangePrefsDialog")
    dlg = Mock()
    Dlg.return_value = dlg
    dlg.exec_.return_value = dlg_result

    global_prefs.change_prefs_dialog()
    assert dlg.save_prefs.called == saved
