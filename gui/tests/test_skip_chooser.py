import pytest
from PySide2.QtCore import Qt
from PySide2.QtGui import QCloseEvent
from PySide2.QtWidgets import QMessageBox

from mozregression.build_range import BuildRange, FutureBuildInfo
from mozregui.skip_chooser import SkipDialog


class DialogBuilder(object):
    def __init__(self, qtbot):
        self.qtbot = qtbot

    def build(self, nb_builds, return_exec_code=SkipDialog.Accepted):
        class FInfo(FutureBuildInfo):
            def _fetch(self):
                return self.data

        build_range = BuildRange(None, [FInfo(None, i) for i in range(nb_builds)])
        dialog = SkipDialog(build_range)
        dialog.exec_ = lambda: return_exec_code
        self.qtbot.addWidget(dialog)
        dialog.show()
        self.qtbot.waitForWindowShown(dialog)
        return dialog


@pytest.fixture
def dialog_builder(qtbot):
    return DialogBuilder(qtbot)


def test_skip_dialog_init(qtbot, dialog_builder):
    dialog = dialog_builder.build(79)
    assert len(dialog.scene.items()) == 79
    mid_item = dialog.scene.mid_build
    assert dialog.build_index(mid_item) == int(79 / 2)
    assert dialog.scene.selectedItems() == [mid_item]


def test_skip_dialog_ok(qtbot, dialog_builder):
    dialog = dialog_builder.build(50)
    # this should block the ui in reality
    assert dialog.choose_next_build() == 50 / 2


def test_dbl_click_btn(qtbot, dialog_builder):
    dialog = dialog_builder.build(50)

    # find the build_item 3
    build_item = None
    for item in dialog.scene.items():
        if dialog.build_index(item) == 3:
            build_item = item
            break
    assert build_item
    dialog.ui.gview.ensureVisible(build_item)
    spos = build_item.mapToScene(build_item.boundingRect().center())
    vpos = dialog.ui.gview.mapFromScene(spos)
    qtbot.mouseMove(dialog.ui.gview.viewport(), vpos)
    qtbot.mouseClick(dialog.ui.gview.viewport(), Qt.LeftButton, pos=vpos)
    items = dialog.scene.selectedItems()
    assert items == [build_item]

    with qtbot.waitSignal(dialog.accepted, raising=False):
        qtbot.mouseDClick(dialog.ui.gview.viewport(), Qt.LeftButton, pos=vpos)
    assert dialog.choose_next_build() == 3


@pytest.mark.parametrize("close", [True, False])
def test_close_event(mocker, dialog_builder, close):
    dialog = dialog_builder.build(5)
    warning = mocker.patch("PySide2.QtWidgets.QMessageBox.warning")
    warning.return_value = QMessageBox.Yes if close else QMessageBox.No
    evt = QCloseEvent()

    dialog.closeEvent(evt)
    assert evt.isAccepted() is close
