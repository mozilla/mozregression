# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import re


class ApproxPersistChooser(object):
    """
    ApproxPersistChooser is able to pick a persistent file that is *near*
    the one we should download.

    For example, if you pass 7 for the *one_every* parameter, it will search
    for builds around the one we need in this way:

    0 if len(bisection range) is < 7
    1 if len(bisection range) is >= 7 and < 14
    2 if len(bisection range) is >= 14 and < 21
    ...

    So if the desired nightly build is 2015-07-10 and the bisection range is
    2015-07-05 - 2015-07-15, this will try to locate a persitent file from
    (in this order):

    2015-07-9
    2015-07-11
    """
    def __init__(self, one_every):
        self.one_every = abs(one_every)

    def _iter(self, build_range, build_info):
        """
        iterate over the possible file name regexes that can match
        an approx build, without the exact filename
        """
        around = len(build_range) / self.one_every
        index = build_range.index(build_info)

        def date_or_chset(next_index):
            # Return the date (for nightlies) or the changeset (for
            # taskcluster) associated with the FutureBuildInfo at the
            # given index.
            return build_info.persist_filename_for(
                # get_future can raise IndexError if we are out of bounds
                build_range.get_future(next_index).date_or_changeset()
            )

        first, last = 0, len(build_range) - 1
        for i in xrange(1, around + 1):
            try:
                next_index = index - i
                if next_index > first:
                    yield next_index, date_or_chset(next_index)
            except IndexError:
                pass
            try:
                next_index = index + i
                if next_index < last:
                    yield next_index, date_or_chset(next_index)
            except IndexError:
                pass

    def index(self, build_range, build_info, filenames):
        """
        Return the index in the build range that can be used to locate
        the approx build_info, or None if none can be found.
        """
        for index, fname in self._iter(build_range, build_info):
            reg = re.compile(fname)
            for other in filenames:
                if reg.match(other):
                    return index
