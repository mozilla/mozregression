import os
import tempfile

import pytest
from mock import Mock
from PySide6.QtWidgets import QDialog

from mozregui import global_prefs


@pytest.fixture
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
    write_default_conf("""
http-timeout = 32.1
persist-size-limit = 2.5
""")

    pref_dialog = global_prefs.ChangePrefsDialog()
    qtbot.add_widget(pref_dialog)
    pref_dialog.show()
    with qtbot.waitExposed(pref_dialog):
        pass

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
    dlg.exec.return_value = dlg_result

    global_prefs.change_prefs_dialog()
    assert dlg.save_prefs.called == saved


def test_temp_dir_pref_is_saved_and_applied(write_default_conf, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", None)
    write_default_conf("")

    pref_dialog = global_prefs.ChangePrefsDialog()
    qtbot.add_widget(pref_dialog)
    assert str(pref_dialog.ui.temp_dir.line_edit.text()) == ""
    assert pref_dialog.ui.temp_dir.line_edit.placeholderText() == "System default"

    pref_dialog.ui.temp_dir.line_edit.setText(str(tmp_path))
    pref_dialog.save_prefs()
    prefs = global_prefs.get_prefs()
    assert prefs["temp_dir"] == str(tmp_path)

    global_prefs.apply_prefs(prefs)
    assert os.path.dirname(tempfile.mkdtemp()) == str(tmp_path)

    pref_dialog.ui.temp_dir.line_edit.setText("")
    pref_dialog.save_prefs()
    global_prefs.apply_prefs(global_prefs.get_prefs())
    assert tempfile.tempdir is None


def test_invalid_temp_dir_is_rejected(write_default_conf, qtbot, tmp_path, mocker):
    write_default_conf("")
    warning = mocker.patch("mozregui.global_prefs.QMessageBox.warning")

    pref_dialog = global_prefs.ChangePrefsDialog()
    qtbot.add_widget(pref_dialog)
    pref_dialog.ui.temp_dir.line_edit.setText(str(tmp_path / "missing"))
    pref_dialog.accept()

    assert warning.called
    assert pref_dialog.result() != QDialog.Accepted


def test_apply_prefs_checks_temp_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", None)
    monkeypatch.setenv("HOME", str(tmp_path))
    prefs = {"http_timeout": 30.0, "temp_dir": "~"}

    global_prefs.apply_prefs(prefs)
    assert tempfile.tempdir == str(tmp_path)

    prefs["temp_dir"] = str(tmp_path / "missing")
    global_prefs.apply_prefs(prefs)
    assert tempfile.tempdir is None
