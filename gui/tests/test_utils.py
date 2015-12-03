import pytest
import datetime

from mozregui.utils import RangeSelection
from mozregression.errors import DateFormatError


@pytest.fixture
def range_selection(qtbot):
    widget = RangeSelection()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitForWindowShown(widget)
    return widget


def test_date_widget_is_visible_by_default(range_selection):
    assert range_selection.select_combo.currentText() == 'date'
    assert range_selection.datew.isVisible()
    assert not range_selection.buildidw.isVisible()
    assert not range_selection.releasew.isVisible()


def test_switch_to_release_widget(range_selection, qtbot):
    qtbot.keyClicks(range_selection.select_combo, "release")
    assert range_selection.select_combo.currentText() == 'release'
    assert not range_selection.datew.isVisible()
    assert not range_selection.buildidw.isVisible()
    assert range_selection.releasew.isVisible()


@pytest.mark.parametrize("widname,value,expected", [
    ("date", "20000101", datetime.date(2000, 1, 1)),
    ("buildid", "20150102101112",
     datetime.datetime(2015, 1, 2, 10, 11, 12)),
    ("release", "40", datetime.date(2015, 5, 11)),
    ("changeset", "abc123", "abc123"),
])
def test_get_value(range_selection, qtbot, widname, value, expected):
    qtbot.keyClicks(range_selection.select_combo, widname)
    qtbot.keyClicks(range_selection.stacked.currentWidget(), value)
    assert range_selection.get_value() == expected


def test_get_invalid_buildid(range_selection, qtbot):
    qtbot.keyClicks(range_selection.select_combo, "buildid")
    qtbot.keyClicks(range_selection.stacked.currentWidget(), "12345")
    with pytest.raises(DateFormatError) as ctx:
        range_selection.get_value()
    assert 'build id' in str(ctx.value)
