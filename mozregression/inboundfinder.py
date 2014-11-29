import mozinfo
import sys
from optparse import OptionParser
import requests
import copy
from mozlog.structured import get_default_logger

from mozregression.build_data import InboundBuildData
from mozregression.utils import url_links

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

        data = sorted(build_urls_in_range, key=lambda b: b[1])

        raw_revisions = [push['changesets'][-1] for push in pushlogs]
        return InboundBuildData(data, raw_revisions)


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
