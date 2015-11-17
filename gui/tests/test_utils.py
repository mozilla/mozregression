import pytest
import datetime

from mozregui.utils import NightlyInputSelection
from mozregression.errors import DateFormatError


@pytest.fixture
def pref_editor(qtbot):
    widget = NightlyInputSelection()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitForWindowShown(widget)
    return widget


def test_date_widget_is_visible_by_default(pref_editor):
    assert pref_editor.select_combo.currentText() == 'date'
    assert pref_editor.datew.isVisible()
    assert not pref_editor.buildidw.isVisible()
    assert not pref_editor.releasew.isVisible()


def test_switch_to_release_widget(pref_editor, qtbot):
    qtbot.keyClicks(pref_editor.select_combo, "release")
    assert pref_editor.select_combo.currentText() == 'release'
    assert not pref_editor.datew.isVisible()
    assert not pref_editor.buildidw.isVisible()
    assert pref_editor.releasew.isVisible()


@pytest.mark.parametrize("widname,value,expected", [
    ("date", "20000101", datetime.date(2000, 1, 1)),
    ("buildid", "20150102101112",
     datetime.datetime(2015, 1, 2, 10, 11, 12)),
    ("release", "40", datetime.date(2015, 5, 11)),
])
def test_get_date(pref_editor, qtbot, widname, value, expected):
    qtbot.keyClicks(pref_editor.select_combo, widname)
    qtbot.keyClicks(pref_editor.stacked.currentWidget(), value)
    assert pref_editor.get_date() == expected


def test_get_invalid_buildid(pref_editor, qtbot):
    qtbot.keyClicks(pref_editor.select_combo, "buildid")
    qtbot.keyClicks(pref_editor.stacked.currentWidget(), "12345")
    with pytest.raises(DateFormatError) as ctx:
        pref_editor.get_date()
    assert 'build id' in str(ctx.value)
