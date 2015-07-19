# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest
from test_build_data import create_nightly_build_data, \
    create_inbound_build_data
from mozregression.build_info import NightlyBuildInfo, InboundBuildInfo
from datetime import date


def create_inbound_build_info(good, bad):
    build_data = create_inbound_build_data(good, bad)
    index = len(build_data) / 2
    build_data._cache[index][0] = {'build_url': 'http://stuff',
                                   'changeset': '123456789abcdefg'}
    return InboundBuildInfo(build_data.fetch_config,
                            build_data,
                            index)


def test_inbound_prefix():
    build_info = create_inbound_build_info('c10', 'c20')
    assert build_info.build_fname() == \
        '123456789abc--mozilla-inbound--stuff'


def test_inbound_iter_prefixes():
    build_info = create_inbound_build_info('c10', 'c20')
    # always one entry for now.
    assert list(build_info.iter_prefixes(15)) == \
        ['123456789abc--mozilla-inbound--']


def create_nightly_build_info(good_date, bad_date):
    build_data = create_nightly_build_data(good_date, bad_date)
    index = len(build_data) / 2
    build_data._cache[index][0] = {'build_url': 'http://stuff'}
    return NightlyBuildInfo(build_data.fetch_config,
                            build_data,
                            index)


def test_nightly_prefix():
    build_info = create_nightly_build_info(date(2015, 07, 01),
                                           date(2015, 07, 11))
    assert build_info.build_fname() == \
        '2015-07-06--mozilla-central--stuff'


@pytest.mark.parametrize("around,result", [
    (0, ['2015-07-03--mozilla-central--']),
    (1, ['2015-07-03--mozilla-central--',
         '2015-07-02--mozilla-central--',
         '2015-07-04--mozilla-central--']),
    (2, ['2015-07-03--mozilla-central--',
         '2015-07-02--mozilla-central--',
         '2015-07-04--mozilla-central--',
         '2015-07-01--mozilla-central--']),
])
def test_iter_prefixes(around, result):
    build_info = create_nightly_build_info(date(2015, 07, 01),
                                           date(2015, 07, 04))
    assert list(build_info.iter_prefixes(around)) == result


@pytest.mark.parametrize("files,around,result", [
    # no files, no result
    ([], 2, None),
    # invalid file names, no result
    (['toto'], 58, None),
    # out of range file names, no result
    (['2010-07-06--mozilla-central--firefox-linux-x86_64.tar.bz2'],
     58, None),
    # exact match, with around 2
    (['2015-07-06--mozilla-central--firefox-linux-x86_64.tar.bz2'],
     2,
     '2015-07-06--mozilla-central--firefox-linux-x86_64.tar.bz2'),
    # exact match, with around 0
    (['2015-07-06--mozilla-central--firefox-linux-x86_64.tar.bz2'],
     0,
     '2015-07-06--mozilla-central--firefox-linux-x86_64.tar.bz2'),
    # one day before with around 1
    (['2015-07-05--mozilla-central--firefox-linux-x86_64.tar.bz2'],
     1,
     '2015-07-05--mozilla-central--firefox-linux-x86_64.tar.bz2'),
    # one day before with around 0, no result
    (['2015-07-05--mozilla-central--firefox-linux-x86_64.tar.bz2'],
     0, None),
    # now we have 3 days before, and one day after - the later
    # is preferred
    (['2015-07-03--mozilla-central--firefox-linux-x86_64.tar.bz2',
      '2015-07-07--mozilla-central--firefox-linux-x86_64.tar.bz2'],
     5,
     '2015-07-07--mozilla-central--firefox-linux-x86_64.tar.bz2'),
])
def test_find_nearest(files, around, result):
    build_info = create_nightly_build_info(date(2015, 07, 01),
                                           date(2015, 07, 11))
    assert build_info.find_nearest_build_file(files, around) == result
