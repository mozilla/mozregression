"""
This module offers an API to get information for one build.

The public API is composed of two classes, :class:`NightlyInfoFetcher` and
:class:`IntegrationInfoFetcher`, able to return
:class:`mozregression.build_info.BuildInfo` instances.
"""

from __future__ import absolute_import

import os
import re
from datetime import datetime
from threading import Lock, Thread

import taskcluster
from mozlog import get_proxy_logger
from requests import HTTPError
from taskcluster.exceptions import TaskclusterFailure

from mozregression.build_info import IntegrationBuildInfo, NightlyBuildInfo
from mozregression.errors import BuildInfoNotFound, MozRegressionError
from mozregression.json_pushes import JsonPushes, Push
from mozregression.network import retry_get, url_links

LOG = get_proxy_logger(__name__)


class InfoFetcher(object):
    def __init__(self, fetch_config):
        self.fetch_config = fetch_config
        self.build_regex = re.compile(fetch_config.build_regex())
        self.build_info_regex = re.compile(fetch_config.build_info_regex())

    def _update_build_info_from_txt(self, build_info):
        LOG.debug("Update build info from {}".format(build_info))
        if "build_txt_url" in build_info:
            build_info.update(self._fetch_txt_info(build_info["build_txt_url"]))

    def _fetch_txt_info(self, url):
        """
        Retrieve information from a build information txt file.

        Returns a dict with keys repository and changeset if information
        is found.
        """
        LOG.debug("Fetching txt info from {}".format(url))
        data = {}
        response = retry_get(url)
        for line in response.text.splitlines():
            if "/rev/" in line:
                repository, changeset = line.split("/rev/")
                data["repository"] = repository
                data["changeset"] = changeset
                break
        if not data:
            # the txt file could be in an old format:
            # DATE CHANGESET
            # we can try to extract that to get the changeset at least.
            matched = re.match(r"^\d+ (\w+)$", response.text.strip())
            if matched:
                data["changeset"] = matched.group(1)
        return data

    def find_build_info(self, changeset_or_date, fetch_txt_info=True):
        """
        Abstract method to retrieve build information over the internet for
        one build.

        This returns a :class:`BuildInfo` instance that contain build
        information.

        Note that this method may raise :class:`BuildInfoNotFound` on error.
        """
        raise NotImplementedError


class IntegrationInfoFetcher(InfoFetcher):
    def __init__(self, fetch_config):
        InfoFetcher.__init__(self, fetch_config)
        self.jpushes = JsonPushes(branch=fetch_config.integration_branch)
        options = fetch_config.tk_options()
        self.index = taskcluster.Index(options)
        self.queue = taskcluster.Queue(options)

    def find_build_info(self, push):
        """
        Find build info for an integration build, given a Push, a changeset or a
        date/datetime.

        if `push` is not an instance of Push (e.g. it is a date, datetime, or
        string representing the changeset), a query to json pushes will be
        done.

        Return a :class:`IntegrationBuildInfo` instance.
        """
        if not isinstance(push, Push):
            try:
                push = self.jpushes.push(push)
            except MozRegressionError as exc:
                raise BuildInfoNotFound(str(exc))

        changeset = push.changeset

        tk_routes = self.fetch_config.tk_routes(push)
        try:
            task_id = None
            stored_failure = None
            for tk_route in tk_routes:
                LOG.debug("using taskcluster route %r" % tk_route)
                try:
                    task_id = self.index.findTask(tk_route)["taskId"]
                except TaskclusterFailure as ex:
                    LOG.debug("nothing found via route %r" % tk_route)
                    stored_failure = ex
                    continue
                if task_id:
                    status = self.queue.status(task_id)["status"]
                    break
            if not task_id:
                raise stored_failure
        except TaskclusterFailure:
            raise BuildInfoNotFound(
                "Unable to find build info using the"
                " taskcluster route %r" % self.fetch_config.tk_route(push)
            )

        # find a completed run for that task
        run_id, build_date = None, None
        for run in reversed(status["runs"]):
            if run["state"] == "completed":
                run_id = run["runId"]
                try:
                    build_date = datetime.strptime(run["resolved"], "%Y-%m-%dT%H:%M:%S.%fZ")
                except ValueError:
                    build_date = datetime.strptime(run["resolved"], "%Y-%m-%dT%H:%M:%S.%f+00:00")
                break

        if run_id is None:
            raise BuildInfoNotFound("Unable to find completed runs for task %s" % task_id)
        artifacts = self.queue.listArtifacts(task_id, run_id)["artifacts"]

        # look over the artifacts of that run
        build_url = None
        for a in artifacts:
            name = os.path.basename(a["name"])
            if self.build_regex.search(name):
                meth = self.queue.buildUrl
                if self.fetch_config.tk_needs_auth():
                    meth = self.queue.buildSignedUrl
                build_url = meth("getArtifact", task_id, run_id, a["name"])
                break
        if build_url is None:
            raise BuildInfoNotFound(
                "unable to find a build url for the" " changeset %r" % changeset
            )
        return IntegrationBuildInfo(
            self.fetch_config,
            build_url=build_url,
            build_date=build_date,
            changeset=changeset,
            repo_url=self.jpushes.repo_url,
            task_id=task_id,
        )


class NightlyInfoFetcher(InfoFetcher):
    def __init__(self, fetch_config):
        InfoFetcher.__init__(self, fetch_config)
        self._cache_months = {}
        self._lock = Lock()
        self._fetch_lock = Lock()

    def _fetch_build_info_from_url(self, url, index, lst):
        """
        Retrieve information from a build folder url.

        Stores in a list the url index and a dict instance with keys
        build_url and build_txt_url if respectively a build file and a
        build info file are found for the url.
        """
        LOG.debug("Fetching build info from {}".format(url))
        data = {}
        if not url.endswith("/"):
            url += "/"
        links = url_links(url)
        if not self.fetch_config.has_build_info:
            links += url_links(self.fetch_config.get_nightly_info_url(url))
        for link in links:
            name = os.path.basename(link)
            if "build_url" not in data and self.build_regex.match(name):
                data["build_url"] = link
            elif "build_txt_url" not in data and self.build_info_regex.match(name):
                data["build_txt_url"] = link
        if data:
            # Check that we found all required data. The URL in build_url is
            # required. build_txt_url is optional.
            if "build_url" not in data:
                raise BuildInfoNotFound(
                    "Failed to find a build file in directory {} that "
                    "matches regex '{}'".format(url, self.build_regex.pattern)
                )

            with self._fetch_lock:
                lst.append((index, data))

    def _get_month_links(self, url):
        with self._lock:
            if url not in self._cache_months:
                self._cache_months[url] = url_links(url)
            return self._cache_months[url]

    def _get_urls(self, date):
        """
        Get the url list of the build folder for a given date.

        This methods needs to be thread-safe as it is used in
        :meth:`NightlyBuildData.get_build_url`.
        """
        LOG.debug("Get URLs for {}".format(date))
        url = self.fetch_config.get_nightly_base_url(date)
        link_regex = re.compile(self.fetch_config.get_nightly_repo_regex(date))

        month_links = self._get_month_links(url)

        # first parse monthly list to get correct directory
        matches = []
        for dirlink in month_links:
            if link_regex.search(dirlink):
                matches.append(dirlink)
        # the most recent build urls first
        matches.reverse()
        return matches

    def find_build_info(self, date, fetch_txt_info=True, max_workers=2):
        """
        Find build info for a nightly build, given a date.

        Returns a :class:`NightlyBuildInfo` instance.
        """
        # getting a valid build for a given date on nightly is tricky.
        # there is multiple possible builds folders for one date,
        # and some of them may be invalid (without binary for example)

        # to save time, we will try multiple build folders at the same
        # time in some threads. The first good one found is returned.
        try:
            build_urls = self._get_urls(date)
            LOG.debug("got build_urls %s" % build_urls)
        except HTTPError as exc:
            raise BuildInfoNotFound(str(exc))
        build_info = None

        valid_builds = []
        while build_urls:
            some = build_urls[:max_workers]
            threads = [
                Thread(target=self._fetch_build_info_from_url, args=(url, i, valid_builds))
                for i, url in enumerate(some)
            ]
            for thread in threads:
                thread.daemon = True
                thread.start()
            for thread in threads:
                while thread.is_alive():
                    thread.join(0.1)
            LOG.debug("got valid_builds %s" % valid_builds)
            if valid_builds:
                infos = sorted(valid_builds, key=lambda b: b[0])[0][1]
                if fetch_txt_info:
                    self._update_build_info_from_txt(infos)

                build_info = NightlyBuildInfo(
                    self.fetch_config,
                    build_url=infos["build_url"],
                    build_date=date,
                    changeset=infos.get("changeset"),
                    repo_url=infos.get("repository"),
                )
                break
            build_urls = build_urls[max_workers:]

        if build_info is None:
            raise BuildInfoNotFound("Unable to find build info for %s" % date)

        return build_info
