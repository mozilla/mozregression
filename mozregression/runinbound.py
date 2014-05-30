import re
import sys
import mozinfo
from optparse import OptionParser

from mozregression.runnightly import FennecNightly, FirefoxNightly, \
    NightlyRunner, parse_bits
from mozregression.inboundfinder import get_build_base_url
from mozregression.utils import url_links, strsplit, get_date


class FirefoxInbound(FirefoxNightly):

    repo_name = None

    def __init__(self, bits=mozinfo.bits, persist=None):
        self.persist = persist
        self.build_regex = self._get_build_regex(self.name, bits)
        self.bits = bits

    def get_build_url(self, timestamp):
        url = "%s%s/" % (get_build_base_url(bits=self.bits), timestamp)
        matches = []
        for link in url_links(url):
            href = link.get("href")
            if re.match(self.build_regex, href):
                matches.append(url + href)
        matches.sort()
        return matches[-1]  # the most recent build url

    def get_repo_name(self, date):
        return "mozilla-inbound"


class FennecInbound(FennecNightly):

    repo_name = None

    def __init__(self, persist=None):
        self.persist = persist

    def get_build_url(self, timestamp):
        url = "%s%s/" % (get_build_base_url(app_name=self.app_name), timestamp)
        matches = []
        for link in url_links(url):
            href = link.get("href")
            if re.match(self.build_regex, href):
                matches.append(url + href)
        matches.sort()
        return matches[-1]  # the most recent build url

    def get_repo_name(self, date):
        return "mozilla-inbound"


class InboundRunner(NightlyRunner):

    def __init__(self, addons=None, appname="firefox", repo_name=None,
                 profile=None, cmdargs=(), bits=mozinfo.bits, persist=None):
        if appname == 'firefox':
            self.app = FirefoxInbound(bits=bits, persist=persist)
        else:
            self.app = FennecInbound(persist=persist)
        self.app_name = appname
        self.bits = bits
        self.addons = addons
        self.profile = profile
        self.persist = persist
        self.cmdargs = list(cmdargs)

    def print_resume_info(self, last_good_revision, first_bad_revision):
        print 'mozregression --good-rev=%s --bad-rev=%s%s' % (
            last_good_revision, first_bad_revision, self.get_resume_options())


def cli(args=sys.argv[1:]):
    parser = OptionParser()
    parser.add_option("--timestamp", dest="timestamp", help="timestamp of "
                      "inbound build")
    parser.add_option("-a", "--addons", dest="addons",
                      help="list of addons to install",
                      metavar="PATH1,PATH2")
    parser.add_option("-p", "--profile", dest="profile",
                      help="path to profile to user", metavar="PATH")
    parser.add_option("--bits", dest="bits",
                      help="force 32 or 64 bit version (only applies to"
                      " x86_64 boxes)",
                      choices=("32", "64"), default=mozinfo.bits)
    parser.add_option("--persist", dest="persist",
                      help="the directory in which files are to persist"
                      " ie. /Users/someuser/Documents")

    options, args = parser.parse_args(args)
    if not options.timestamp:
        print "timestamp must be specified"
        sys.exit(1)
    options.bits = parse_bits(options.bits)
    # XXX https://github.com/mozilla/mozregression/issues/50
    addons = strsplit(options.addons or "", ",")
    runner = InboundRunner(addons=addons, profile=options.profile,
                           bits=options.bits, persist=options.persist)
    runner.start(get_date(options.date))
    try:
        runner.wait()
    except KeyboardInterrupt:
        runner.stop()

if __name__ == "__main__":
    cli()
