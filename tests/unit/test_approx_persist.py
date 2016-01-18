import pytest
from test_build_info import create_build_info

from mozregression import build_info, approx_persist, build_range


def create_build_range(values):
    info_fetcher = None  # we should not need to access it

    data = []
    for v in values:
        data.append(build_range.FutureBuildInfo(
            info_fetcher, v
        ))
    return build_range.BuildRange(info_fetcher, data)


def build_firefox_name(chset):
    return ('%s--mozilla-inbound--firefox-38.0a1.en-US.linux-x86_64.tar.bz2'
            % chset)


def build_firefox_names(chsets):
    return [build_firefox_name(c) for c in chsets]


@pytest.mark.parametrize('bdata, mid, around, fnames, result', [
    # index is None when there is no files
    ('0123456789', None, 7, [], None),
    # one file around works
    ('0123456789', None, 7, build_firefox_names('4'), 4),
    ('0123456789', None, 7, build_firefox_names('6'), 6),
    # with 10 builds, two files around returns None
    ('0123456789', None, 7, build_firefox_names('123789'), None),
    # same with 13
    ('0123456789abc', None, 7, build_firefox_names('8'), None),
    # but 14 will give a result
    ('0123456789abcd', None, 7, build_firefox_names('8'), 8),
    # we never overflow
    ('0123456789', 8, 4, [], None),
    ('0123456789', 1, 4, [], None),
])
def test_approx_index(bdata, mid, around, fnames, result):
    # this is always a firefox 64 linux build info
    binfo = create_build_info(build_info.InboundBuildInfo)
    brange = create_build_range(bdata)
    brange.index = lambda _: mid or len(bdata)/2
    approx = approx_persist.ApproxPersistChooser(around)

    assert approx.index(brange, binfo, fnames) == result
