# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os


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

    def persist_prefix(self):
        raise NotImplementedError

    def build_fname(self):
        """Return the filename of the build (without the path)"""
        return self.persist_prefix() + os.path.basename(self['build_url'])


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

    def persist_prefix(self):
        return '{date}--{repo}--'.format(date=self['build_date'],
                                         repo=self['repo'])


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

    def persist_prefix(self):
        return '{chset}--{repo}--'.format(chset=self['changeset'][:12],
                                          repo=self['repo'])
