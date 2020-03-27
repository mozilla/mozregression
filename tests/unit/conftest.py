import pytest

from mozregression import build_range
from mozregression.fetch_build_info import InfoFetcher


class RangeCreator(object):
    def __init__(self, mocker):
        self.mocker = mocker

    def create(self, values):
        info_fetcher = self.mocker.Mock(spec=InfoFetcher)
        info_fetcher.find_build_info.side_effect = lambda i: i
        future_build_infos = [build_range.FutureBuildInfo(info_fetcher, v) for v in values]
        return build_range.BuildRange(info_fetcher, future_build_infos)


@pytest.fixture
def range_creator(mocker):
    return RangeCreator(mocker)
