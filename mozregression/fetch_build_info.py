"""
This module offers an API to get information for one build.

The public API is composed of two classes, :class:`NightlyInfoFetcher` and
:class:`InboundInfoFetcher`. they both inherit from the :class:`InfoFetcher`.

Here is an example of usage, to get the build url of builds::

  from datetime import date
  from mozregression.fetch_config import create_config

  fetch_config = create_config('firefox', 'linux', 64)
  # note that you should configure the fetch_config to use another repo
  # than the defaut one for the application.

  # find build info for one date (looks in nightly builds)
  info_fetcher = NightlyInfoFetcher(fetch_config)
  print info_fetcher.find_build_info(date(2015, 01, 01))['build_url']

  # find build info for one changeset (looks in inbound builds)
  info_fetcher = InboundInfoFetcher(fetch_config)
  print info_fetcher.find_build_info("a_valid_changeset")['build_url']
"""

import os
import re
import threading
import taskcluster
from taskcluster.exceptions import TaskclusterFailure
from mozlog.structuredlog import get_default_logger
from concurrent import futures

from mozregression.network import url_links, retry_get
from mozregression.errors import BuildInfoNotFound


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

        This returns a dict that contain build information. At minima, this
        contains the key "build_url" that is the url of the build to download.

        If available (it *should*, but this is not ensured) there will be
        also the key "build_txt_url", that is the url of the .txt file
        corresponding to the build file.

        if *fetch_txt_info* is True, this .txt file will be read to try to
        get two following keys:

         - "repository": the name of the repository where the source for the
           build lives (ie, mozilla-central).
         - "changeset": the changeset used in that repository to build the
           sources.

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
        """
        tk_route = self.fetch_config.tk_inbound_route(changeset)
        self._logger.debug('using taskcluster route %r' % tk_route)
        try:
            task = self.index.findTask(tk_route)
        except TaskclusterFailure:
            raise BuildInfoNotFound("Unable to find build info using the"
                                    " taskcluster route %r" % tk_route)
        artifacts = self.queue.listLatestArtifacts(task['taskId'])['artifacts']
        data = {}
        for a in artifacts:
            match = None
            name = os.path.basename(a['name'])
            if self.build_regex.match(name):
                match = 'build_url'
            elif self.build_info_regex.match(name):
                match = 'build_txt_url'
            if match:
                data[match] = self.queue.buildUrl(
                    'getLatestArtifact',
                    task['taskId'],
                    a['name']
                )
        if 'build_url' not in data:
            raise BuildInfoNotFound("unable to find a build url for the"
                                    " changeset %r" % changeset)
        if fetch_txt_info:
            self._update_build_info_from_txt(data)
        return data


class NightlyInfoFetcher(InfoFetcher):
    def __init__(self, fetch_config):
        InfoFetcher.__init__(self, fetch_config)
        self._cache_months = {}
        self._lock = threading.Lock()

    def _fetch_build_info_from_url(self, url):
        """
        Retrieve information from a build folder url.

        Returns a dict with keys build_url and build_txt_url if respectively
        a build file and a build info file are found for the url.
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
        """
        # getting a valid build for a given date on nightly is tricky.
        # there is multiple possible builds folders for one date,
        # and some of them may be invalid (without binary for example)

        # to save time, we will try multiple build folders at the same
        # time in some threads. The first good one found is returned.
        build_urls = self._get_urls(date)
        build_infos = None

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
                    build_infos = sorted(valid_builds,
                                         key=lambda b: b[0])[0][1]
                    break
            build_urls = build_urls[max_workers:]

        if build_infos is None:
            raise BuildInfoNotFound("Unable to find build info for %s" % date)

        if fetch_txt_info:
            self._update_build_info_from_txt(build_infos)
        return build_infos
