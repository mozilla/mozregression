from mock import Mock
from PySide2.QtCore import Qt

from mozregression.build_info import NightlyBuildInfo
from mozregui.report import ReportView


def test_report_basic(qtbot):
    view = ReportView()
    qtbot.addWidget(view)

    # TODO: rewrite all this.

    slot = Mock()
    view.step_report_changed.connect(slot)
    # show the widget
    view.show()
    qtbot.waitForWindowShown(view)
    # start the bisection
    view.model().started()
    view.model().step_started(Mock())
    # a row is inserted
    index = view.model().index(0, 0)
    assert index.isValid()

    # simulate a build found
    data = dict(build_type="nightly", build_date="date", repo_name="mozilla-central")
    build_infos = Mock(spec=NightlyBuildInfo, to_dict=lambda: data, **data)
    bisection = Mock(build_range=[Mock(repo_name="mozilla-central")])
    bisection.handler.find_fix = False
    bisection.handler.get_range.return_value = ("1", "2")
    view.model().step_build_found(bisection, build_infos)
    # now we have two rows
    assert view.model().rowCount() == 2
    # data is updated
    index2 = view.model().index(1, 0)
    assert "[1 - 2]" in view.model().data(index)
    assert "mozilla-central" in view.model().data(index2)

    # simulate a build evaluation
    view.model().step_finished(None, "g")
    # still two rows
    assert view.model().rowCount() == 2
    # data is updated
    assert "g" in view.model().data(index2)

    # let's click on the index
    view.scrollTo(index)
    rect = view.visualRect(index)
    qtbot.mouseClick(view.viewport(), Qt.LeftButton, pos=rect.center())
    # signal has been emitted
    assert slot.call_count == 1

    # let's simulate another bisection step
    bisection.handler.get_pushlog_url.return_value = "http://pl"
    view.model().step_started(bisection)
    assert view.model().rowCount() == 3
    # then say that it's the end
    view.model().finished(bisection, None)
    # this last row is removed now
    assert view.model().rowCount() == 2
