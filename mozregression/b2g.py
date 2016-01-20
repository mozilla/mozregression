# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os

from mozregression.errors import MozRegressionError


def _evaluate_gecko_and_gaia(gecko_info, gaia_info, dest):
    print 'Please flash and test the following files on your device:'
    print ' - %s [gecko]' % os.path.join(
        dest,
        gecko_info.persist_filename_for(build_key='gecko'))
    print ' - %s [gaia]' % os.path.join(
        dest,
        gaia_info.persist_filename_for(build_key='gaia'))
    print
    res = ''
    while res not in ('g', 'b'):
        res = raw_input('Is it good or broken ? [gb]: ')
    return res


def check_gecko_or_gaia_broken(build_range, download_manager, find_fix=False):
    """
    Detect if we have a gecko or a gaia regression.
    """
    print """

******** End of the bisection, let's determine if gaia or gecko is broken...
"""
    good, bad = build_range[0], build_range[-1]
    if find_fix:
        good, bad = bad, good

    download_manager.focus_download(good, build_key='gecko')
    download_manager.focus_download(bad, build_key='gaia')
    # start downloading next gaia in background, it is a big file
    download_manager.download_in_background(good, build_key='gaia')
    r1 = _evaluate_gecko_and_gaia(good, bad, download_manager.destdir)

    download_manager.focus_download(good, build_key='gaia')
    download_manager.focus_download(bad, build_key='gecko')
    r2 = _evaluate_gecko_and_gaia(bad, good, download_manager.destdir)

    if r1 == 'g' and r2 == 'b':
        print 'gaia is broken !'
    elif r1 == 'b' and r2 == 'g':
        print 'gecko is broken !'
    else:
        raise MozRegressionError(
            "Unable to determine if gecko or gaia is broken..."
        )
