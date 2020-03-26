import tempfile

import mozfile
import pytest
from mock import patch
from PySide2.QtCore import Qt

from mozregui.addons_editor import AddonsWidgetEditor


@pytest.fixture
def addons_editor(qtbot):
    widget = AddonsWidgetEditor()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitForWindowShown(widget)
    return widget


def get_view_focus(addons_editor):
    return addons_editor.ui.list_view.viewport().focusWidget


def test_create_addons_editor(addons_editor):
    assert addons_editor.get_addons() == []


@pytest.fixture
def addons_file(request):
    # create a temp addons file
    f = tempfile.NamedTemporaryFile(suffix=".xpi", dir=".", delete=False)
    f.close()
    request.addfinalizer(lambda: mozfile.remove(f.name))
    return f.name


def test_add_addon(qtbot, addons_editor, addons_file):
    with patch("mozregui.addons_editor.QFileDialog") as dlg:
        filePath = addons_file
        dlg.getOpenFileNames.return_value = ([filePath], "addon file (*.xpi)")
        qtbot.mouseClick(addons_editor.ui.add_addon, Qt.LeftButton)
        dlg.getOpenFileNames.assert_called_once_with(
            addons_editor,
            "Choose one or more addon files",
            filter="addon file (*.xpi)",
        )

        # check addons
        assert addons_editor.list_model.rowCount() == len([filePath])
        assert addons_editor.get_addons() == [filePath]


def test_remove_addon(qtbot, addons_editor, addons_file):
    test_add_addon(qtbot, addons_editor, addons_file)
    addons_editor.ui.list_view.setCurrentIndex(addons_editor.list_model.index(0))
    assert addons_editor.ui.list_view.selectedIndexes()
    qtbot.mouseClick(addons_editor.ui.remove_addon, Qt.LeftButton)

    assert addons_editor.list_model.rowCount() == 0
    assert addons_editor.get_addons() == []
