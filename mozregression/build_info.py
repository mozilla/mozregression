# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import re


class BuildInfo(dict):
    """
    A dict that contain information about a build.

    A BuildInfo is instantiated for each step of the bisection.

    This must be initialized with a :class:`mozregression.build_data.BuildData`
    instance that already have loaded the bisection information for the given
    index.

    A BuildInfo instance hold the following values (as keys of the dict):

     - 'build_type': same as the build_type value passed in the constructor
     - 'app_name': the application name, given by the fetch_config
     - 'build_url': the url of the build file to download, given by the
       build_data object
     - 'repo': the repository name of the mercurial branch (e.g.
               mozilla-central), given by the fetch_config

    Note that subclasses add their own values in there.

    :param build_type: the type of the build, ie 'nighly' or 'inbound'. Must
                       be defined by sub-classes.
    :param fetch_config: the fetch config instance used for the bisection
    :param build_data: a :class:`mozregression.build_data.BuildData` instance
                       that hold information for the whole bisection.
    :param index: the index of the build tested into the build data, e.g
                  `build_data.mid()`.
    """
    def __init__(self, build_type, fetch_config, build_data, index):
        self.fetch_config = fetch_config
        self.build_data = build_data
        self.index = index
        dict.__init__(self)
        self['build_type'] = build_type
        self['app_name'] = fetch_config.app_name
        # merge the build data information of the build
        self.update(build_data[index])

    def _persist_prefix(self, move_index=0):
        raise NotImplementedError

    def iter_prefixes(self, around):
        around = abs(around)
        nb_data = len(self.build_data)
        assert nb_data > 0
        yield self._persist_prefix(0)
        for i in xrange(1, around + 1):
            try:
                yield self._persist_prefix(-i)
            except IndexError:
                pass
            try:
                yield self._persist_prefix(i)
            except IndexError:
                pass

    def find_nearest_build_file(self, files, around):
        """
        Return the nearest file name for this build.

        Given a list of files (what we can found in the persist folder)
        and a "around" parameter, this method return the file that is
        closer to this build.

        The around parameter allow to search for +/- around. For example,
        for a nightly build 2015-07-10, a value of 2 for around will search for
        files from 2015-07-08 to 2015-07-12 included.
        """
        prefix2fname = {}
        for f in files:
            try:
                date_or_chset, repo, fname = f.split('--', 2)
            except ValueError:
                continue
            if re.match(self.fetch_config.build_regex(), fname):
                prefix2fname['%s--%s--' % (date_or_chset, repo)] = f
        for prefix in self.iter_prefixes(around):
            if prefix in prefix2fname:
                return prefix2fname[prefix]

    def build_fname(self):
        """Return the filename of the build (without the path)"""
        return self._persist_prefix() + os.path.basename(self['build_url'])


class NightlyBuildInfo(BuildInfo):
    """
    BuildInfo for nightly bisection.

    This add the following value:

     - 'build_date': the `datetime.date` object representing the build date,
                     given by the build_data object
    """

    def __init__(self, fetch_config, build_data, index):
        BuildInfo.__init__(self, 'nightly', fetch_config, build_data, index)
        self['build_date'] = build_data.get_associated_data(index)
        self['repo'] = fetch_config.get_nightly_repo(self['build_date'])

    def _persist_prefix(self, move_index=0):
        index = self.index + move_index
        date = self.build_data.get_associated_data(index)
        return '{date}--{repo}--'.format(
            date=date,
            repo=self.fetch_config.get_nightly_repo(date))


class InboundBuildInfo(BuildInfo):
    """
    BuildInfo for inbound bisection.

    This add the following value:

     - 'changeset': the changeset id of the build, given by the build_data
                    object
    """

    def __init__(self, fetch_config, build_data, index):
        BuildInfo.__init__(self, 'inbound', fetch_config, build_data, index)
        self['repo'] = fetch_config.inbound_branch

    def _persist_prefix(self, move_index=0):
        return '{chset}--{repo}--'.format(chset=self['changeset'][:12],
                                          repo=self['repo'])

    def iter_prefixes(self, around):
        # not available for inbound now.
        # We should look at InboundBuildData, and inject the
        # mercurial push id in the associated data - so we could
        # build a map chset -> push id and be able to detect
        # previous/next changesets.
        # but first we have to change the behavior of the
        # PushLogFinder that order chsets by time (and not
        # by push ids)
        # TODO check this.
        for prefix in BuildInfo.iter_prefixes(self, 0):
            yield prefix
