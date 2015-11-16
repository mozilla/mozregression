import pytest
from datetime import date, datetime

from mozregression import build_range
from mozregression.fetch_build_info import InfoFetcher
from mozregression.errors import BuildInfoNotFound
from mozregression.fetch_configs import create_config
from mozregression.json_pushes import JsonPushes


class RangeCreator(object):
    def __init__(self, mocker):
        self.mocker = mocker

    def create(self, values):
        info_fetcher = self.mocker.Mock(spec=InfoFetcher)
        info_fetcher.find_build_info.side_effect = lambda i: i
        future_build_infos = [
            build_range.FutureBuildInfo(info_fetcher, v) for v in values
        ]
        return build_range.BuildRange(info_fetcher, future_build_infos)


@pytest.fixture
def range_creator(mocker):
    return RangeCreator(mocker)


def test_len(range_creator):
    assert len(range_creator.create(range(5))) == 5


def test_access(range_creator):
    build_range = range_creator.create(range(5))
    assert build_range[0] == 0

    build_range.build_info_fetcher.find_build_info.side_effect = \
        BuildInfoNotFound
    assert build_range[1] is False

    # even if one build is invalid, item access do not modify the range
    assert len(build_range) == 5
    # but the following will remove the invalid entry
    build_range.filter_invalid_builds()
    assert len(build_range) == 4


def test_slice(range_creator):
    build_range = range_creator.create(range(5))
    build_range2 = build_range[3:]
    assert len(build_range) == 5
    assert len(build_range2) == 2

    assert build_range[3] == 3
    assert build_range2[0] == 3


def test_deleted(range_creator):
    build_range = range_creator.create(range(5))
    build_range2 = build_range.deleted(1)
    assert len(build_range) == 5
    assert len(build_range2) == 4

    assert build_range2[0] == 0
    assert build_range2[1] == 2


def test_mid_point(range_creator):
    build_range = range_creator.create(range(10))

    def fetch(index):
        # last build info can't be fetched
        if index == 9:
            raise BuildInfoNotFound("")
        return index

    build_range.build_info_fetcher.find_build_info.side_effect = fetch

    assert build_range.mid_point() == 4
    assert len(build_range) == 9
    assert [build_range[i] for i in range(9)] == range(9)

    # with a range len < 3, mid is 0.
    assert build_range[:2].mid_point() == 0


def test_index(range_creator):
    build_range = range_creator.create(range(10))
    # no build_info fetched yet, so ValueError is raised
    with pytest.raises(ValueError):
        build_range.index(5)

    mid = build_range.mid_point()
    assert mid == 5
    assert mid == build_range.index(5)


def test_range_for_inbounds(mocker):
    fetch_config = create_config('firefox', 'linux', 64)
    jpush_class = mocker.patch('mozregression.fetch_build_info.JsonPushes')
    jpush = mocker.Mock(
        pushlog_within_changes=mocker.Mock(
            return_value=[{'changesets': ['a', 'b']},
                          {'changesets': ['c', 'd']},
                          {'changesets': ['e', 'f']}]
        ),
        spec=JsonPushes
    )
    jpush_class.return_value = jpush

    b_range = build_range.range_for_inbounds(fetch_config, 'a', 'e')

    jpush_class.assert_called_once_with(branch='mozilla-inbound',
                                        path='integration')
    jpush.pushlog_within_changes.assert_called_once_with('a', 'e')
    assert isinstance(b_range, build_range.BuildRange)
    assert len(b_range) == 3

    b_range.build_info_fetcher.find_build_info = lambda v: v
    assert b_range[0] == 'b'
    assert b_range[1] == 'd'
    assert b_range[2] == 'f'


def test_range_for_nightlies():
    fetch_config = create_config('firefox', 'linux', 64)

    b_range = build_range.range_for_nightlies(
        fetch_config,
        date(2015, 01, 01),
        date(2015, 01, 03)
    )

    assert isinstance(b_range, build_range.BuildRange)
    assert len(b_range) == 3

    b_range.build_info_fetcher.find_build_info = lambda v: v
    assert b_range[0] == date(2015, 01, 01)
    assert b_range[1] == date(2015, 01, 02)
    assert b_range[2] == date(2015, 01, 03)


@pytest.mark.parametrize('start,end,range_size', [
    (datetime(2015, 11, 16, 10, 2, 5), date(2015, 11, 19), 4),
    (date(2015, 11, 14), datetime(2015, 11, 16, 10, 2, 5), 3),
    (datetime(2015, 11, 16, 10, 2, 5),
     datetime(2015, 11, 20, 11, 4, 9), 5),
])
def test_range_for_nightlies_datetime(start, end, range_size):
    fetch_config = create_config('firefox', 'linux', 64)

    b_range = build_range.range_for_nightlies(fetch_config, start, end)

    assert isinstance(b_range, build_range.BuildRange)
    assert len(b_range) == range_size

    b_range.build_info_fetcher.find_build_info = lambda v: v
    assert b_range[0] == start
    assert b_range[-1] == end
    # between, we only have date instances
    for i in range(1, range_size - 1):
        assert isinstance(b_range[i], date)
