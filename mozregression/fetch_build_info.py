"""
This module offers an API to get information for one build.

The public API is composed of two classes, :class:`NightlyInfoFetcher` and
:class:`InboundInfoFetcher`, able to return
:class:`mozregression.build_info.BuildInfo` instances.
"""

import os
import re
import threading
import taskcluster
from datetime import datetime
from taskcluster.exceptions import TaskclusterFailure
from mozlog.structuredlog import get_default_logger
from concurrent import futures

from mozregression.network import url_links, retry_get
from mozregression.errors import BuildInfoNotFound
from mozregression.build_info import NightlyBuildInfo, InboundBuildInfo


class InfoFetcher(object):
    def __init__(self, fetch_config):
        self._logger = get_default_logger(__name__)
        self.fetch_config = fetch_config
        self.build_regex = re.compile(fetch_config.build_regex())
        self.build_info_regex = re.compile(fetch_config.build_info_regex())

    def _update_build_info_from_txt(self, build_info):
        if 'build_txt_url' in build_info:
            build_info.update(
                self._fetch_txt_info(build_info['build_txt_url'])
            )

    def _fetch_txt_info(self, url):
        """
        Retrieve information from a build information txt file.

        Returns a dict with keys repository and changeset if information
        is found.
        """
        data = {}
        response = retry_get(url)
        for line in response.text.splitlines():
            if '/rev/' in line:
                repository, changeset = line.split('/rev/')
                data['repository'] = repository
                data['changeset'] = changeset
                break
        if not data:
            # the txt file could be in an old format:
            # DATE CHANGESET
            # we can try to extract that to get the changeset at least.
            matched = re.match('^\d+ (\w+)$', response.text.strip())
            if matched:
                data['changeset'] = matched.group(1)
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


class InboundInfoFetcher(InfoFetcher):
    def __init__(self, fetch_config):
        InfoFetcher.__init__(self, fetch_config)
        self.index = taskcluster.client.Index()
        self.queue = taskcluster.Queue()

    def find_build_info(self, changeset, fetch_txt_info=True):
        """
        Find build info for an inbound build, given a changeset.

        Return a :class:`InboundBuildInfo` instance.
        """
        # find a task id
        tk_route = self.fetch_config.tk_inbound_route(changeset)
        self._logger.debug('using taskcluster route %r' % tk_route)
        try:
            task_id = self.index.findTask(tk_route)['taskId']
        except TaskclusterFailure:
            raise BuildInfoNotFound("Unable to find build info using the"
                                    " taskcluster route %r" % tk_route)

        # find a completed run for that task
        run_id, build_date = None, None
        status = self.queue.status(task_id)['status']
        for run in reversed(status['runs']):
            if run['state'] == 'completed':
                run_id = run['runId']
                build_date = datetime.strptime(run["resolved"],
                                               '%Y-%m-%dT%H:%M:%S.%fZ')
                break

        if run_id is None:
            raise BuildInfoNotFound("Unable to find completed runs for task %s"
                                    % task_id)
        artifacts = self.queue.listArtifacts(task_id, run_id)['artifacts']
        data = {}

        # look over the artifacts of that run
        for a in artifacts:
            match = None
            name = os.path.basename(a['name'])
            if self.build_regex.search(name):
                match = 'build_url'
            elif self.build_info_regex.match(name):
                match = 'build_txt_url'
            if match:
                data[match] = self.queue.buildUrl(
                    'getLatestArtifact',
                    task_id,
                    a['name']
                )
        if 'build_url' not in data:
            raise BuildInfoNotFound("unable to find a build url for the"
                                    " changeset %r" % changeset)
        if fetch_txt_info:
            self._update_build_info_from_txt(data)
            # keep the most precise changeset.
            if 'changeset' in data and len(data['changeset']) > changeset:
                changeset = data['changeset']
        return InboundBuildInfo(
            self.fetch_config,
            build_url=data['build_url'],
            build_date=build_date,
            changeset=changeset,
            repo_url=data.get('repository')
        )


class NightlyInfoFetcher(InfoFetcher):
    def __init__(self, fetch_config):
        InfoFetcher.__init__(self, fetch_config)
        self._cache_months = {}
        self._lock = threading.Lock()

    def _fetch_build_info_from_url(self, url):
        """
        Retrieve information from a build folder url.

        Returns a :class:`NightlyBuildInfo` instance with keys build_url and
        build_txt_url if respectively a build file and a build info file are
        found for the url.
        """
        data = {}
        if not url.endswith('/'):
            url += '/'
        for link in url_links(url):
            if 'build_url' not in data and self.build_regex.match(link):
                data['build_url'] = url + link
            elif 'build_txt_url' not in data  \
                    and self.build_info_regex.match(link):
                data['build_txt_url'] = url + link

        return data

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
        url = self.fetch_config.get_nighly_base_url(date)
        link_regex = re.compile(self.fetch_config.get_nightly_repo_regex(date))

        month_links = self._get_month_links(url)

        # first parse monthly list to get correct directory
        matches = []
        for dirlink in month_links:
            if link_regex.match(dirlink):
                matches.append(url + dirlink)
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
        build_urls = self._get_urls(date)
        build_info = None

        while build_urls:
            some = build_urls[:max_workers]
            with futures.ThreadPoolExecutor(max_workers=max_workers) \
                    as executor:
                futures_results = {}
                valid_builds = []
                for i, url in enumerate(some):
                    future = executor.submit(self._fetch_build_info_from_url,
                                             url)
                    futures_results[future] = i
                for future in futures.as_completed(futures_results):
                    i = futures_results[future]
                    infos = future.result()
                    if infos:
                        valid_builds.append((i, infos))
                if valid_builds:
                    infos = sorted(valid_builds, key=lambda b: b[0])[0][1]
                    if fetch_txt_info:
                        self._update_build_info_from_txt(infos)

                    build_info = NightlyBuildInfo(
                        self.fetch_config,
                        build_url=infos['build_url'],
                        build_date=date,
                        changeset=infos.get('changeset'),
                        repo_url=infos.get('repository')
                    )
                    break
            build_urls = build_urls[max_workers:]

        if build_info is None:
            raise BuildInfoNotFound("Unable to find build info for %s" % date)

        return build_info
