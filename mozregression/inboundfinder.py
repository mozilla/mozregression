import mozinfo
import sys
from optparse import OptionParser
import requests
import copy

from mozregression.utils import url_links
from concurrent import futures


class PushLogsFinder(object):
    """
    Find pushlog json objects within two revisions.
    """
    def __init__(self, start_rev, end_rev, path='integration',
                 branch='mozilla-inbound'):
        self.start_rev = start_rev
        self.end_rev = end_rev
        self.path = path
        self.branch = branch

    def pushlog_url(self):
        return 'https://hg.mozilla.org/%s/%s/json-pushes' \
            '?fromchange=%s&tochange=%s' % (self.path,
                                            self.branch,
                                            self.start_rev,
                                            self.end_rev)

    def get_pushlogs(self):
        """
        Returns pushlog json objects (python dicts) sorted by date.
        """
        response = requests.get(self.pushlog_url())
        response.raise_for_status()
        # sort pushlogs by date
        return sorted(response.json().itervalues(),
                      key=lambda push: push['date'])


class BuildsFinder(object):
    """
    Find builds information for builds within two revisions.
    """
    def __init__(self, bits=mozinfo.bits, os=mozinfo.os):
        self.bits = bits
        self.os = os
        self.build_base_url = self._get_build_base_url()

    def _create_pushlog_finder(self, start_rev, end_rev):
        return PushLogsFinder(start_rev, end_rev)

    def _get_build_base_url(self):
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

        raw_revisions = [push['changesets'][-1] for push in pushlogs]
        all_builds = []
        with futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures_results = {}
            for build_url, timestamp in build_urls_in_range:
                future = executor.submit(self._get_valid_builds,
                                         build_url,
                                         timestamp,
                                         raw_revisions)
                futures_results[future] = build_url
            for future in futures.as_completed(futures_results):
                if future.exception() is not None:
                    sys.exit("Retrieving valid builds from %r generated an"
                             " exception: %s" % (futures_results[future],
                                                 future.exception()))
                all_builds.extend(future.result())

        return self._sort_builds(all_builds)

    def _sort_builds(self, builds):
        return sorted(builds, key=lambda b: b['timestamp'])

    def _get_valid_builds(self, build_url, timestamp, raw_revisions):
        builds = []
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
                        builds.append({
                            'revision': revision,
                            'timestamp': timestamp,
                        })
        return builds


class FennecBuildsFinder(BuildsFinder):
    def _get_build_base_url(self):
        return "http://inbound-archive.pub.build.mozilla.org/pub/mozilla.org" \
            "/mobile/tinderbox-builds/mozilla-inbound-android/"


class FirefoxBuildsFinder(BuildsFinder):
    build_base_os_part = {
        'linux': {32: 'linux', 64: 'linux64'},
        'win': {32: 'win32'},
        'mac': {64: 'macosx64'}
    }
    root_build_base_url = 'http://inbound-archive.pub.build.mozilla.org/pub' \
            '/mozilla.org/firefox/tinderbox-builds/mozilla-inbound-%s/'

    def _get_build_base_url(self):
        if self.os == "win" and self.bits == 64:
            # XXX this should actually throw an error to be consumed
            # by the caller
            print "No builds available for 64 bit Windows" \
                " (try specifying --bits=32)"
            sys.exit()
        return self.root_build_base_url % self.build_base_os_part[self.os][self.bits]


class B2GBuildsFinder(FirefoxBuildsFinder):
    build_base_os_part = copy.deepcopy(FirefoxBuildsFinder.build_base_os_part)
    build_base_os_part['linux'][32] = 'linux32'
    
    root_build_base_url = 'http://ftp.mozilla.org/pub/mozilla.org/b2g'\
            '/tinderbox-builds/b2g-inbound-%s_gecko/'

    def _create_pushlog_finder(self, start_rev, end_rev):
        return PushLogsFinder(start_rev, end_rev, branch='b2g-inbound')


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

    options, args = parser.parse_args(args)
    if not options.start_rev or not options.end_rev:
        print "start revision and end revision must be specified"
        sys.exit(1)

    build_finders = {
        'firefox': FirefoxBuildsFinder,
        'b2g': B2GBuildsFinder,
        'fennec': FennecBuildsFinder
    }
    
    build_finder = build_finders[options.app](os=options.os, bits=options.bits)
    
    revisions = build_finder.get_build_infos(options.start_rev,
                                             options.end_rev,
                                             range=60*60*12)
    print "Revision, Timestamp"
    for revision in revisions:
        print revision['revision'], revision['timestamp']

if __name__ == "__main__":
    cli()
