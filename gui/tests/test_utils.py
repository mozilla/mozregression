import datetime

import pytest

from mozregression.errors import DateFormatError
from mozregui.utils import BuildSelection


@pytest.fixture
def build_selection(qtbot):
    widget = BuildSelection()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitForWindowShown(widget)
    return widget


def test_date_widget_is_visible_by_default(build_selection):
    assert build_selection.ui.combo_helper.currentText() == "date"
    assert build_selection.ui.date.isVisible()
    assert not build_selection.ui.buildid.isVisible()
    assert not build_selection.ui.release.isVisible()


def test_switch_to_release_widget(build_selection, qtbot):
    qtbot.keyClicks(build_selection.ui.combo_helper, "release")
    assert build_selection.ui.combo_helper.currentText() == "release"
    assert not build_selection.ui.date.isVisible()
    assert not build_selection.ui.buildid.isVisible()
    assert build_selection.ui.release.isVisible()


@pytest.mark.parametrize(
    "widname,value,expected",
    [
        ("buildid", "20150102101112", datetime.datetime(2015, 1, 2, 10, 11, 12)),
        ("buildid", " \t20150102101112  ", datetime.datetime(2015, 1, 2, 10, 11, 12)),
        ("release", "40", datetime.date(2015, 5, 11)),
        ("changeset", "abc123", "abc123"),
        ("changeset", " abc123\t  ", "abc123"),
    ],
)
def test_get_value(build_selection, qtbot, widname, value, expected):
    qtbot.keyClicks(build_selection.ui.combo_helper, widname)
    qtbot.keyClicks(getattr(build_selection.ui, widname), value)
    assert build_selection.get_value() == expected


def test_date_picker(build_selection, qtbot):
    qtbot.keyClicks(build_selection.ui.combo_helper, "date")
    calendarWidget = build_selection.ui.date
    aDate = datetime.date(2000, 1, 1)
    calendarWidget.setDate(aDate)
    assert build_selection.get_value() == aDate


def test_get_invalid_buildid(build_selection, qtbot):
    qtbot.keyClicks(build_selection.ui.combo_helper, "buildid")
    qtbot.keyClicks(build_selection.ui.stackedWidget.currentWidget(), "12345")
    with pytest.raises(DateFormatError) as ctx:
        build_selection.get_value()
    assert "build id" in str(ctx.value)
