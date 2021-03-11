from __future__ import absolute_import

from datetime import date, datetime, timedelta

import pytest

from mozregression import build_range
from mozregression.errors import BuildInfoNotFound
from mozregression.fetch_configs import create_config
from mozregression.json_pushes import JsonPushes

from .test_fetch_configs import create_push


def test_len(range_creator):
    assert len(range_creator.create(list(range(5)))) == 5


def test_access(range_creator):
    build_range = range_creator.create(list(range(5)))
    assert build_range[0] == 0

    build_range.build_info_fetcher.find_build_info.side_effect = BuildInfoNotFound
    assert build_range[1] is False

    # even if one build is invalid, item access do not modify the range
    assert len(build_range) == 5
    # but the following will remove the invalid entry
    build_range.filter_invalid_builds()
    assert len(build_range) == 4


def test_slice(range_creator):
    build_range = range_creator.create(list(range(5)))
    build_range2 = build_range[3:]
    assert len(build_range) == 5
    assert len(build_range2) == 2

    assert build_range[3] == 3
    assert build_range2[0] == 3


def test_deleted(range_creator):
    build_range = range_creator.create(list(range(5)))
    build_range2 = build_range.deleted(1)
    assert len(build_range) == 5
    assert len(build_range2) == 4

    assert build_range2[0] == 0
    assert build_range2[1] == 2


def fetch_unless(br, func):
    def fetch(index):
        if func(index):
            raise BuildInfoNotFound("")
        return index

    br.build_info_fetcher.find_build_info.side_effect = fetch


def test_mid_point(range_creator):
    build_range = range_creator.create(list(range(10)))
    fetch_unless(build_range, lambda i: i == 9)

    assert build_range.mid_point() == 4
    assert len(build_range) == 9
    assert [build_range[i] for i in range(9)] == list(range(9))

    # with a range len < 3, mid is 0.
    assert build_range[:2].mid_point() == 0


def test_mid_point_interrupt(range_creator):
    build_range = range_creator.create(list(range(10)))
    assert build_range.mid_point(interrupt=lambda: False) == 5
    with pytest.raises(StopIteration):
        build_range.mid_point(interrupt=lambda: True)


def _build_range(fb, rng):
    return build_range.BuildRange(
        fb.build_info_fetcher,
        [build_range.FutureBuildInfo(fb.build_info_fetcher, i) for i in rng],
    )


def range_before(fb, expand):
    return _build_range(fb, list(range(fb.data - expand, fb.data)))


def range_after(fb, expand):
    return _build_range(fb, list(range(fb.data + 1, fb.data + 1 + expand)))


@pytest.mark.parametrize(
    "size_expand,initial,fail_in,expected,error",
    [
        # short range
        (10, list(range(1)), [], list(range(1)), None),
        # empty range after removing invalids
        (10, list(range(2)), [0, 1], [], None),
        # lower limit missing
        (10, list(range(10)), [0], [-1] + list(range(1, 10)), None),
        # higher limit missing
        (10, list(range(10)), [9], list(range(0, 9)) + [10], None),
        # lower and higher limit missing
        (10, list(range(10)), [0, 9], [-1] + list(range(1, 9)) + [10], None),
        # lower missing, with missing builds in the before range
        (10, list(range(10)), list(range(-5, 1)), [-6] + list(range(1, 10)), None),
        # higher missing, with missing builds in the after range
        (10, list(range(10)), list(range(9, 15)), list(range(0, 9)) + [15], None),
        # lower and higher missing, with missing builds in the before/after range
        (
            10,
            list(range(10)),
            list(range(-6, 1)) + list(range(9, 14)),
            [-7] + list(range(1, 9)) + [14],
            None,
        ),
        # unable to find any valid builds in before range
        (
            10,
            list(range(10)),
            list(range(-10, 1)),
            list(range(1, 10)),
            ["can't find a build before"],
        ),
        # unable to find any valid builds in after range
        (
            10,
            list(range(10)),
            list(range(9, 20)),
            list(range(0, 9)),
            ["can't find a build after"],
        ),
        # unable to find valid builds in before and after
        (
            10,
            list(range(10)),
            list(range(-10, 1)) + list(range(9, 20)),
            list(range(1, 9)),
            ["can't find a build before", "can't find a build after"],
        ),
    ],
)
def test_check_expand(mocker, range_creator, size_expand, initial, fail_in, expected, error):
    log = mocker.patch("mozregression.build_range.LOG")
    build_range = range_creator.create(initial)
    fetch_unless(build_range, lambda i: i in fail_in)

    build_range.check_expand(size_expand, range_before, range_after)

    assert [b for b in build_range] == expected
    if error:
        assert log.critical.called
        for i, call in enumerate(log.critical.call_args_list):
            assert error[i] in call[0][0]


def test_check_expand_interrupt(range_creator):
    build_range = range_creator.create(list(range(10)))
    fetch_unless(build_range, lambda i: i == 0)

    mp = build_range.mid_point
    build_range.mid_point = lambda **kwa: mp()  # do not interrupt in there

    with pytest.raises(StopIteration):
        build_range.check_expand(5, range_before, range_after, interrupt=lambda: True)


def test_index(range_creator):
    build_range = range_creator.create(list(range(10)))
    # no build_info fetched yet, so ValueError is raised
    with pytest.raises(ValueError):
        build_range.index(5)

    mid = build_range.mid_point()
    assert mid == 5
    assert mid == build_range.index(5)


def test_get_integration_range(mocker):
    fetch_config = create_config("firefox", "linux", 64, "x86_64")
    jpush_class = mocker.patch("mozregression.fetch_build_info.JsonPushes")
    pushes = [create_push("b", 1), create_push("d", 2), create_push("f", 3)]
    jpush = mocker.Mock(pushes_within_changes=mocker.Mock(return_value=pushes), spec=JsonPushes)
    jpush_class.return_value = jpush

    b_range = build_range.get_integration_range(fetch_config, "a", "e")

    jpush_class.assert_called_once_with(branch="mozilla-central")
    jpush.pushes_within_changes.assert_called_once_with("a", "e")
    assert isinstance(b_range, build_range.BuildRange)
    assert len(b_range) == 3

    b_range.build_info_fetcher.find_build_info = lambda v: v
    assert b_range[0] == pushes[0]
    assert b_range[1] == pushes[1]
    assert b_range[2] == pushes[2]

    b_range.future_build_infos[0].date_or_changeset() == "b"


def test_get_integration_range_with_expand(mocker):
    fetch_config = create_config("firefox", "linux", 64, "x86_64")
    jpush_class = mocker.patch("mozregression.fetch_build_info.JsonPushes")
    pushes = [create_push("b", 1), create_push("d", 2), create_push("f", 3)]
    jpush = mocker.Mock(pushes_within_changes=mocker.Mock(return_value=pushes), spec=JsonPushes)
    jpush_class.return_value = jpush

    check_expand = mocker.patch("mozregression.build_range.BuildRange.check_expand")

    build_range.get_integration_range(fetch_config, "a", "e", expand=10)

    check_expand.assert_called_once_with(
        10, build_range.tc_range_before, build_range.tc_range_after, interrupt=None
    )


DATE_NOW = datetime.now()
DATE_BEFORE_NOW = DATE_NOW + timedelta(days=-5)
DATE_YEAR_BEFORE = DATE_NOW + timedelta(days=-365)
DATE_TOO_OLD = DATE_YEAR_BEFORE + timedelta(days=-5)


@pytest.mark.parametrize(
    "start_date,end_date,start_call,end_call",
    [
        (DATE_BEFORE_NOW, DATE_NOW, DATE_BEFORE_NOW, DATE_NOW),
        # if a date is older than last year, it won't be honored
        (DATE_TOO_OLD, DATE_NOW, DATE_YEAR_BEFORE, DATE_NOW),
    ],
)
def test_get_integration_range_with_dates(mocker, start_date, end_date, start_call, end_call):
    fetch_config = create_config("firefox", "linux", 64, "x86_64")
    jpush_class = mocker.patch("mozregression.fetch_build_info.JsonPushes")
    jpush = mocker.Mock(pushes_within_changes=mocker.Mock(return_value=[]), spec=JsonPushes)
    jpush_class.return_value = jpush

    build_range.get_integration_range(
        fetch_config, start_date, end_date, time_limit=DATE_YEAR_BEFORE
    )

    jpush.pushes_within_changes.assert_called_once_with(start_call, end_call)


def test_get_nightly_range():
    fetch_config = create_config("firefox", "linux", 64, "x86_64")

    b_range = build_range.get_nightly_range(fetch_config, date(2015, 1, 1), date(2015, 1, 3))

    assert isinstance(b_range, build_range.BuildRange)
    assert len(b_range) == 3

    b_range.build_info_fetcher.find_build_info = lambda v: v
    assert b_range[0] == date(2015, 1, 1)
    assert b_range[1] == date(2015, 1, 2)
    assert b_range[2] == date(2015, 1, 3)


@pytest.mark.parametrize(
    "start,end,range_size",
    [
        (datetime(2015, 11, 16, 10, 2, 5), date(2015, 11, 19), 4),
        (date(2015, 11, 14), datetime(2015, 11, 16, 10, 2, 5), 3),
        (datetime(2015, 11, 16, 10, 2, 5), datetime(2015, 11, 20, 11, 4, 9), 5),
    ],
)
def test_get_nightly_range_datetime(start, end, range_size):
    fetch_config = create_config("firefox", "linux", 64, "x86_64")

    b_range = build_range.get_nightly_range(fetch_config, start, end)

    assert isinstance(b_range, build_range.BuildRange)
    assert len(b_range) == range_size

    b_range.build_info_fetcher.find_build_info = lambda v: v
    assert b_range[0] == start
    assert b_range[-1] == end
    # between, we only have date instances
    for i in range(1, range_size - 1):
        assert isinstance(b_range[i], date)


@pytest.mark.parametrize(
    "func,start,size,expected_range",
    [
        (build_range.tc_range_before, 1, 2, [-1, 0]),
        (build_range.tc_range_after, 1, 3, list(range(2, 5))),
    ],
)
def test_tc_range_before_after(mocker, func, start, size, expected_range):
    ftc = build_range.FutureBuildInfo(mocker.Mock(), mocker.Mock(push_id=start))

    def pushes(startID, endID):
        # startID: greaterThan  -  endID: up to and including
        # http://mozilla-version-control-tools.readthedocs.org/en/latest/hgmo/pushlog.html#query-parameters  # noqa
        return list(range(startID + 1, endID + 1))

    ftc.build_info_fetcher.jpushes.pushes.side_effect = pushes
    rng = func(ftc, size)
    assert len(rng) == size
    assert [rng.get_future(i).data for i in range(len(rng))] == expected_range
