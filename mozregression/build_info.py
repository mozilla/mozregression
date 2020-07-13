"""
The BuildInfo classes, that are used to store information a build.
"""
from __future__ import absolute_import

import datetime
import re
from urllib.parse import urlparse

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

    def __init__(
        self,
        fetch_config,
        build_type,
        build_url,
        build_date,
        changeset,
        repo_url,
        repo_name,
        task_id=None,
    ):
        self._fetch_config = fetch_config
        self._build_type = build_type
        self._build_url = build_url
        self._build_date = build_date
        self._changeset = changeset
        self._repo_url = repo_url
        self._repo_name = repo_name
        self._build_file = None
        self._task_id = task_id

    @property
    @export
    def build_type(self):
        """
        Either 'nightly' or 'integration'
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

    @property
    @export
    def task_id(self):
        """
        The task ID, for Taskcluster builds.
        """
        return self._task_id

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
            self._changeset = app_info.get("application_changeset")
        if self._repo_url is None:
            self._repo_url = app_info.get("application_repository")

    def persist_filename_for(self, data, regex=True):
        """
        Returns the persistent filename for the given data.

        `data` should be a date or datetime object if the build type is
        'nightly', else a changeset.

        if `regex` is True, instead of returning the persistent filename
        it is returned a string (regex pattern) that can match a filename.
        The pattern only allows the build name to be different, by using
        the fetch_config.build_regex() value. For example, it can return:

        '2015-01-11--mozilla-central--firefox.*linux-x86_64\\.tar.bz2$'
        """
        if self.build_type == "nightly":
            if isinstance(data, datetime.datetime):
                prefix = data.strftime("%Y-%m-%d-%H-%M-%S")
            else:
                prefix = str(data)
            persist_part = ""
        else:
            prefix = str(data[:12])
            persist_part = self._fetch_config.integration_persist_part()
        if persist_part:
            persist_part = "-" + persist_part
        extra = self._fetch_config.extra_persist_part()
        if extra:
            extra = extra + "--"
        full_prefix = "{}{}--{}--{}".format(prefix, persist_part, self.repo_name, extra)
        if regex:
            full_prefix = re.escape(full_prefix)
            appname = self._fetch_config.build_regex()
        else:
            appname = urlparse(self.build_url).path.replace("%2F", "/").split("/")[-1]
        return "{}{}".format(full_prefix, appname)

    @property
    def persist_filename(self):
        """
        Compute and return the persist filename to use to store this build.
        """
        if self.build_type == "nightly":
            data = self.build_date
        else:
            data = self.changeset
        return self.persist_filename_for(data, regex=False)

    def to_dict(self):
        """
        Export some public properties as a dict.
        """
        return dict((field, getattr(self, field)) for field in FIELDS)


class NightlyBuildInfo(BuildInfo):
    def __init__(self, fetch_config, build_url, build_date, changeset, repo_url):
        BuildInfo.__init__(
            self,
            fetch_config,
            "nightly",
            build_url,
            build_date,
            changeset,
            repo_url,
            fetch_config.get_nightly_repo(build_date),
        )


class IntegrationBuildInfo(BuildInfo):
    def __init__(self, fetch_config, build_url, build_date, changeset, repo_url, task_id=None):
        BuildInfo.__init__(
            self,
            fetch_config,
            "integration",
            build_url,
            build_date,
            changeset,
            repo_url,
            fetch_config.integration_branch,
            task_id=task_id,
        )
