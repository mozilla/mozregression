import tempfile

import mozfile
import pytest
from mock import patch
from PySide2.QtCore import Qt

from mozregui.pref_editor import PreferencesWidgetEditor


@pytest.fixture
def pref_editor(qtbot):
    widget = PreferencesWidgetEditor()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitForWindowShown(widget)
    return widget


def get_view_focus(pref_editor):
    return pref_editor.ui.pref_view.viewport().focusWidget()


def test_create_pref_editor(pref_editor):
    # no prefs on creation
    assert pref_editor.get_prefs() == []


def test_add_empty_pref_then_fill_it(qtbot, pref_editor):
    # click on add_pref
    qtbot.mouseClick(pref_editor.ui.add_pref, Qt.LeftButton)
    # we should be in edit mode
    edit_widget = get_view_focus(pref_editor)
    assert edit_widget

    # type the name of the property
    qtbot.keyClicks(edit_widget, "hello")

    # hit tab to edit the value
    qtbot.keyClick(edit_widget, Qt.Key_Tab)

    edit_widget = get_view_focus(pref_editor)

    # type the value
    qtbot.keyClicks(edit_widget, "world")

    # now finish the editing
    qtbot.keyClick(edit_widget, Qt.Key_Tab)

    # check prefs
    assert pref_editor.pref_model.rowCount() == 1
    assert len(pref_editor.get_prefs()) == 1
    # FIXME: the next line fails, need to figure out why
    # assert pref_editor.get_prefs() == [("hello", "world")]


def test_remove_pref(qtbot, pref_editor):
    # first add a pref
    test_add_empty_pref_then_fill_it(qtbot, pref_editor)

    # select the row
    pref_editor.ui.pref_view.selectRow(0)
    assert pref_editor.ui.pref_view.selectedIndexes()

    # now click on the button to delete the row
    qtbot.mouseClick(pref_editor.ui.remove_selected_prefs, Qt.LeftButton)

    # pref have been removed
    assert pref_editor.pref_model.rowCount() == 0
    assert pref_editor.get_prefs() == []


@pytest.fixture
def pref_file(request):
    # create a temp file with prefs
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        f.write(b'{ "browser.tabs.remote.autostart": false, "toto": 1 }')
    request.addfinalizer(lambda: mozfile.remove(f.name))
    return f.name


def test_add_prefs_using_file(qtbot, pref_editor, pref_file):
    with patch("mozregui.pref_editor.QFileDialog") as dlg:
        dlg.getOpenFileName.return_value = (pref_file, "pref file (*.json *.ini)")
        qtbot.mouseClick(pref_editor.ui.add_prefs_from_file, Qt.LeftButton)
    dlg.getOpenFileName.assert_called_once_with(
        pref_editor, "Choose a preference file", filter="pref file (*.json *.ini)"
    )

    # check prefs
    assert pref_editor.pref_model.rowCount() == 2
    assert set(pref_editor.get_prefs()) == set(
        [("browser.tabs.remote.autostart", False), ("toto", 1)]
    )
