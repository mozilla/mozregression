# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
The BuildInfo classes, that are used to store information a build.
"""


FIELDS = []


def export(func):
    FIELDS.append(func.__name__)
    return func


class BuildInfo(object):
    """
    Store information about a build to be able to download and run it.

    a BuildInfo is built by calling
    :meth:`mozregression.fetch_build_info.FetchBuildInfo.find_build_info`.
    """
    def __init__(self, fetch_config, build_type, build_url, build_date,
                 changeset, repo_url, repo_name):
        self._fetch_config = fetch_config
        self._build_type = build_type
        self._build_url = build_url
        self._build_date = build_date
        self._changeset = changeset
        self._repo_url = repo_url
        self._repo_name = repo_name
        self._build_file = None

    @property
    @export
    def build_type(self):
        """
        Either 'nightly' or 'inbound'
        """
        return self._build_type

    @property
    @export
    def app_name(self):
        """
        The application name, such as "firefox"
        """
        return self._fetch_config.app_name

    @property
    @export
    def build_url(self):
        """
        The url to download the build
        """
        return self._build_url

    @property
    @export
    def build_date(self):
        """
        The date of the build
        """
        return self._build_date

    @property
    @export
    def changeset(self):
        """
        The changeset of the build. For old nightlies, this can be None.
        """
        return self._changeset

    @property
    @export
    def repo_url(self):
        """
        The url of the repository. For old nightlies, this can be None.
        """
        return self._repo_url

    @property
    @export
    def repo_name(self):
        """
        the repository name, e.g. 'mozilla-central'
        """
        return self._repo_name

    @property
    @export
    def build_file(self):
        """
        The build file, once downloaded. This property is None when the
        BuildInfo is instanciated and should be set later.
        """
        return self._build_file

    @build_file.setter
    def build_file(self, build_file):
        self._build_file = build_file

    @property
    def short_changeset(self):
        """
        Returns the first 8 characters of the build changeset.
        """
        return self.changeset[:8]

    def update_from_app_info(self, app_info):
        """
        Takes an app_info (as returned by mozversion) and update the build info
        content if required.

        This helps to build the pushlog url for old nightlies.
        """
        if self._changeset is None:
            self._changeset = app_info.get('application_changeset')
        if self._repo_url is None:
            self._repo_url = app_info.get('application_repository')

    def to_dict(self):
        """
        Export some public properties as a dict.
        """
        return dict((field, getattr(self, field)) for field in FIELDS)


class NightlyBuildInfo(BuildInfo):
    def __init__(self, fetch_config, build_url, build_date, changeset,
                 repo_url):
        BuildInfo.__init__(self, fetch_config, 'nightly', build_url,
                           build_date, changeset, repo_url,
                           fetch_config.get_nightly_repo(build_date))


class InboundBuildInfo(BuildInfo):
    def __init__(self, fetch_config, build_url, build_date, changeset,
                 repo_url):
        BuildInfo.__init__(self, fetch_config, 'inbound', build_url,
                           build_date, changeset, repo_url,
                           fetch_config.inbound_branch)
