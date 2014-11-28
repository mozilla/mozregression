import mozinfo
import sys
from optparse import OptionParser
import requests
import copy
from mozlog.structured import get_default_logger

from mozregression import errors
from mozregression.utils import url_links
from concurrent import futures

def get_repo_url(path='integration', inbound_branch='mozilla-inbound'):
    return "https://hg.mozilla.org/%s/%s" % (path, inbound_branch)

class PushLogsFinder(object):
    """
    Find pushlog json objects within two revisions.
    """
    def __init__(self, start_rev, end_rev, path='integration',
                 inbound_branch='mozilla-inbound'):
        self.start_rev = start_rev
        self.end_rev = end_rev
        self.path = path
        self.inbound_branch = inbound_branch

    def pushlog_url(self):
        return '%s/json-pushes?fromchange=%s&tochange=%s' % (
            get_repo_url(self.path, self.inbound_branch),
            self.start_rev, self.end_rev)

    def get_pushlogs(self):
        """
        Returns pushlog json objects (python dicts) sorted by date.
        """
        response = requests.get(self.pushlog_url())
        response.raise_for_status()
        # sort pushlogs by date
        return sorted(response.json().itervalues(),
                      key=lambda push: push['date'])


class InboundBuildData(object):
    """
    Represents the inbound build data avalaible, designed to be used in
    bisection.

    It allow the lazy loading of build data, by fetching only lower bound,
    higher bound and middle points when required.

    As some build folders are not valid - and we can know that only
    after really fetching data - there is some imprecision on data
    size which may reduce when you call ensure_limits or mid_point.

    An instance of InboundBuildData acts like a list, ensuring following
    methods:
     - len(data) # size
     - data[1:]  # splice
     - data[0]   # get data
    """
    def __init__(self, cache, raw_revisions, half_window_range=4):
        self._cache = cache
        self.raw_revisions = raw_revisions
        self.half_window_range = half_window_range
        self._logger = get_default_logger('Inbound Build Finder')

    def __len__(self):
        return len(self._cache)

    def __getslice__(self, smin, smax):
        return InboundBuildData(self._cache[smin:smax],
                               self.raw_revisions,
                               half_window_range=self.half_window_range)

    def __getitem__(self, i):
        return self._cache[i][0]

    def ensure_limits(self):
        """
        Ensure we know the min and max data, fetching it if necessary.
        """
        done = False
        while not done:
            size = len(self)
            if size == 0:
                # no limits to ensure
                return

            # first we detect if we need to fetch data, and which build id's
            range_min = []
            range_max = []

            # we first get an artifically large range (double) to optimize
            # the number of build data which will be fetched.
            #
            # this way, if we have a self.half_window_range of 4 (the default)
            # and for example we don't need the lowest bound, the number of
            # data to fetch for higher bound will be 8 (full range) instead
            # of 4.
            if self[0] is None:
                self._logger.debug("We need to fetch the inbound lower limit")
                bound = min(size, self.half_window_range*2)
                range_min.extend(range(0, bound))
            if self[-1] is None:
                self._logger.debug("We need to fetch the inbound higher limit")
                bound = max(0, size - self.half_window_range*2)
                range_max.extend(range(bound, size))

            # restrict the number of builds to fetch
            range_to_update = set(range_min + range_max)
            while len(range_to_update) > self.half_window_range*2:
                if len(range_min) > len(range_max):
                    range_min = range_min[:-1]
                else:
                    range_max = range_max[1:]
                range_to_update = set(range_min + range_max)

            if range_to_update:
                self._fetch(range_to_update)
                # we asked for some data, but it may be not suficient -
                # data may be invalid - let's check it by looping
            else:
                # data is fetched on min and max bounds, we can exit
                done = True

    def mid_point(self):
        """
        Return the middle index of the data. If 0, there is no middle
        point anymore.
        """
        while True:
            self.ensure_limits()

            size = len(self)
            mid = size / 2
            if mid == 0:
                return 0

            if self[mid] is None:
                self._logger.debug('We need to fetch the inbound mid point %d'
                                   % mid)
                # we need to fetch the middle of the data
                rmax = min(size, mid + self.half_window_range)
                rmin = max(0, mid - self.half_window_range)
                self._fetch(range(rmin, rmax))
                # maybe all fetched data was invalid and we need to
                # check it by looping
            else:
                return mid

    def _fetch(self, ids, max_retry=3):
        """
        Internal method to fetch some data.
        """
        # filter the already downloaded data
        builds_to_get = [i for i in ids if self[i] is None]
        size = len(self)
        self._logger.debug("We got %d inbound folders, we need to fetch %s"
                           % (size, sorted(builds_to_get)))

        nb_try = 0
        while builds_to_get:
            nb_try += 1
            with futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures_results = {}
                for i in builds_to_get:
                    build_url, timestamp = self._cache[i][1], self._cache[i][2]
                    future = executor.submit(self._get_valid_build,
                                             build_url,
                                             timestamp,
                                             self.raw_revisions)
                    futures_results[future] = i
                for future in futures.as_completed(futures_results):
                    i = futures_results[future]
                    exc = future.exception()
                    if exc is not None:
                        must_raise = True
                        if isinstance(exc, requests.HTTPError):
                            if nb_try < max_retry:
                                self._logger.warning("Got HTTPError - retrying")
                                must_raise = False
                        if must_raise:
                            raise errors.DownloadError(
                                "Retrieving valid builds from %r generated an"
                                " exception: %s" % (self._cache[i][1],
                                                    exc))
                    else:
                        builds_to_get.remove(i)
                        self._cache[i][0] = future.result()
        # filter the builds that were invalids
        self._cache = [c for c in self._cache if c[0] is not False]
        self._logger.debug("Now we got %d inbound folders - %d were bad"
                           % (len(self), size - len(self)))

    def _get_valid_build(self, build_url, timestamp, raw_revisions):
        for link in url_links(build_url, regex=r'^.+\.txt$'):
            url = "%s/%s" % (build_url, link)
            response = requests.get(url)
            remote_revision = None
            for line in response.iter_lines():
                # Filter out Keep-Alive new lines.
                if not line:
                    continue
                parts = line.split('/rev/')
                if len(parts) == 2:
                    remote_revision = parts[1]
                    break  # for line
            if remote_revision:
                for revision in raw_revisions:
                    if remote_revision in revision:
                        return {
                            'revision': revision[:8],
                            'timestamp': timestamp,
                        }
        return False


class BuildsFinder(object):
    """
    Find builds information for builds within two revisions.
    """
    def __init__(self, bits=mozinfo.bits, os=mozinfo.os,
                 inbound_branch=None):
        self.bits = bits
        self.os = os
        self.inbound_branch = inbound_branch or self.default_inbound_branch
        self.build_base_url = self._get_build_base_url(self.inbound_branch)

    def _create_pushlog_finder(self, start_rev, end_rev):
        return PushLogsFinder(start_rev, end_rev,
                              inbound_branch=self.inbound_branch)

    def _get_build_base_url(self, inbound_branch):
        raise NotImplementedError()

    def _extract_paths(self):
        paths = filter(lambda l: l.isdigit(),
                       map(lambda l: l.strip('/'),
                           url_links(self.build_base_url)))
        return [(p, int(p)) for p in paths]

    def get_build_infos(self, start_rev, end_rev, range=60*60*4):
        """
        Returns build information for all builds between start_rev and end_rev
        """
        pushlogs_finder = self._create_pushlog_finder(start_rev, end_rev)

        pushlogs = pushlogs_finder.get_pushlogs()

        if not pushlogs:
            return []

        start_time = pushlogs[0]['date']
        end_time = pushlogs[-1]['date']
        
        build_urls = [("%s%s/" % (self.build_base_url, path), timestamp)
                      for path, timestamp in self._extract_paths()]

        build_urls_in_range = filter(lambda (u, t): t > (start_time - range)
                                     and t < (end_time + range), build_urls)
        # build empty cache
        cache = []
        for url, timestamp in sorted(build_urls_in_range, key=lambda b: b[1]):
            cache.append([None, url, timestamp])

        raw_revisions = [push['changesets'][-1] for push in pushlogs]
        return InboundBuildData(cache, raw_revisions)


class FennecBuildsFinder(BuildsFinder):
    default_inbound_branch = 'mozilla-inbound'

    def _get_build_base_url(self, inbound_branch):
        return "http://inbound-archive.pub.build.mozilla.org/pub/mozilla.org" \
            "/mobile/tinderbox-builds/%s-android/" % inbound_branch


class FirefoxBuildsFinder(BuildsFinder):
    build_base_os_part = {
        'linux': {32: 'linux', 64: 'linux64'},
        'win': {32: 'win32', 64: 'win64'},
        'mac': {64: 'macosx64'}
    }
    root_build_base_url = 'http://inbound-archive.pub.build.mozilla.org/pub' \
            '/mozilla.org/firefox/tinderbox-builds/%s-%s/'
    default_inbound_branch = 'mozilla-inbound'

    def _get_build_base_url(self, inbound_branch):
        return self.root_build_base_url % \
                (inbound_branch, self.build_base_os_part[self.os][self.bits])


class B2GBuildsFinder(FirefoxBuildsFinder):
    build_base_os_part = copy.deepcopy(FirefoxBuildsFinder.build_base_os_part)
    build_base_os_part['linux'][32] = 'linux32'
    root_build_base_url = 'http://ftp.mozilla.org/pub/mozilla.org/b2g'\
            '/tinderbox-builds/%s-%s_gecko/'
    default_inbound_branch = 'b2g-inbound'


def cli(args=sys.argv[1:]):

    parser = OptionParser()
    parser.add_option("--start-rev", dest="start_rev", help="start revision")
    parser.add_option("--end-rev", dest="end_rev", help="end revision")
    parser.add_option("--os", dest="os", help="override operating system "
                      "autodetection (mac, linux, win)", default=mozinfo.os)
    parser.add_option("--bits", dest="bits", help="override operating system "
                      "bits autodetection", default=mozinfo.bits)
    parser.add_option("-n", "--app", dest="app", help="application name "
                      "(firefox, fennec or b2g)",
                      metavar="[firefox|fennec|b2g]",
                      default="firefox")
    parser.add_option("--inbound-branch", dest="inbound_branch",
                      help="inbound branch name on ftp.mozilla.org",
                      metavar="[tracemonkey|mozilla-1.9.2]", default=None)

    options, args = parser.parse_args(args)
    if not options.start_rev or not options.end_rev:
        sys.exit("start revision and end revision must be specified")

    build_finders = {
        'firefox': FirefoxBuildsFinder,
        'b2g': B2GBuildsFinder,
        'fennec': FennecBuildsFinder
    }
    
    if options.inbound_branch:
        inbound_branch = options.inbound_branch
    else:
        inbound_branch = build_finder.default_inbound_branch

    build_finder = build_finders[options.app](os=options.os, bits=options.bits,
                                              inbound_branch=inbound_branch)
    
    revisions = build_finder.get_build_infos(options.start_rev,
                                             options.end_rev,
                                             range=60*60*12)
    print("Revision, Timestamp")
    for revision in revisions:
        print("%s %s" % (revision['revision'], revision['timestamp']))

if __name__ == "__main__":
    cli()
