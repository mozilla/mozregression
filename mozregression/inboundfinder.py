import mozinfo
import sys
from optparse import OptionParser
from mozregression import limitedfilecache
from mozlog.structured import get_default_logger

from mozregression.build_data import InboundBuildData, BuildFolderInfoFetcher
from mozregression.utils import url_links, get_http_session, set_http_cache_session

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
        # the first changeset is not taken into account in the result.
        # let's add it directly with this request
        chset_url = '%s/json-pushes?changeset=%s' % (
            get_repo_url(self.path, self.inbound_branch),
            self.start_rev)
        response = get_http_session().get(chset_url)
        response.raise_for_status()
        chsets = response.json()

        # now fetch all remaining changesets
        response = get_http_session().get(self.pushlog_url())
        response.raise_for_status()
        chsets.update(response.json())
        # sort pushlogs by date
        return sorted(chsets.itervalues(),
                      key=lambda push: push['date'])


class BuildsFinder(object):
    """
    Find builds information for builds within two revisions.
    """
    def __init__(self, fetch_config):
        self.fetch_config = fetch_config

    def _create_pushlog_finder(self, start_rev, end_rev):
        return PushLogsFinder(start_rev, end_rev,
                              inbound_branch=self.fetch_config.inbound_branch)

    def _extract_paths(self):
        paths = filter(lambda l: l.isdigit(),
                       map(lambda l: l.strip('/'),
                           url_links(self.fetch_config.inbound_base_url())))
        return [(p, int(p)) for p in paths]

    def get_build_infos(self, start_rev, end_rev, range=60*60*4):
        """
        Returns build information for all builds between start_rev and end_rev
        """
        pushlogs_finder = self._create_pushlog_finder(start_rev, end_rev)

        pushlogs = pushlogs_finder.get_pushlogs()

        if not pushlogs:
            return InboundBuildData([], None, [])

        start_time = pushlogs[0]['date']
        end_time = pushlogs[-1]['date']
        
        build_urls = [("%s%s/" % (self.fetch_config.inbound_base_url(),
                                  path), timestamp)
                      for path, timestamp in self._extract_paths()]

        build_urls_in_range = filter(lambda b: b[1] > (start_time - range)
                                     and b[1] < (end_time + range), build_urls)

        data = sorted(build_urls_in_range, key=lambda b: b[1])

        info_fetcher = BuildFolderInfoFetcher(self.fetch_config.build_regex(),
                                              self.fetch_config.build_info_regex())

        raw_revisions = [push['changesets'][-1] for push in pushlogs]
        return InboundBuildData(data, info_fetcher, raw_revisions)


def get_build_finder(args):
    from mozregression.fetch_configs import create_config
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
    parser.add_option("--http-cache-dir", dest="http_cache_dir",
                      help="the directory for caching http requests")

    options, args = parser.parse_args(args)
    if not options.start_rev or not options.end_rev:
        sys.exit("start revision and end revision must be specified")

    fetch_config = create_config(options.app, options.os, options.bits)

    cacheSession = limitedfilecache.get_cache(
        options.http_cache_dir, limitedfilecache.ONE_GIGABYTE,
        logger=get_default_logger('Limited File Cache'))

    set_http_cache_session(cacheSession)

    return BuildsFinder(fetch_config)

def cli(args=sys.argv[1:]):
    build_finder = get_build_finder(args)
    revisions = build_finder.get_build_infos(options.start_rev,
                                             options.end_rev,
                                             range=60*60*12)
    print("Revision, Timestamp")
    for revision in revisions:
        print("%s %s" % (revision['revision'], revision['timestamp']))

if __name__ == "__main__":
    cli()
