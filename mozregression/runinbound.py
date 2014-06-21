import sys
import mozinfo
from optparse import OptionParser

from mozregression.runnightly import FennecNightly, FirefoxNightly, \
    B2GNightly, NightlyRunner, parse_bits
from mozregression.inboundfinder import FirefoxBuildsFinder, \
    FennecBuildsFinder, B2GBuildsFinder
from mozregression.utils import url_links, get_date


class FirefoxInbound(FirefoxNightly):

    repo_name = None

    def __init__(self, bits=mozinfo.bits, persist=None):
        self.persist = persist
        self.build_regex = self._get_build_regex(self.name, bits)
        self.bits = bits
        self.build_finder = FirefoxBuildsFinder(bits=bits)

    def get_build_url(self, timestamp):
        base_url = "%s%s/" % (self.build_finder.build_base_url, timestamp)
        matches = [base_url + url
                   for url in url_links(base_url, regex=self.build_regex)]
        matches.sort()
        return matches[-1]  # the most recent build url

    def get_repo_name(self, date):
        return "mozilla-inbound"


class FennecInbound(FennecNightly):

    repo_name = None

    def __init__(self, persist=None):
        self.persist = persist
        self.build_finder = FennecBuildsFinder()

    def get_build_url(self, timestamp):
        base_url = "%s%s/" % (self.build_finder.build_base_url, timestamp)
        matches = [base_url + url
                   for url in url_links(base_url, regex=self.build_regex)]
        matches.sort()
        return matches[-1]  # the most recent build url

    def get_repo_name(self, date):
        return "mozilla-inbound"


class B2GInbound(B2GNightly):

    repo_name = None

    def __init__(self, **kwargs):
        B2GNightly.__init__(self, **kwargs)
        self.build_finder = B2GBuildsFinder(bits=self.bits)

    def get_build_url(self, timestamp):
        base_url = "%s%s/" % (self.build_finder.build_base_url, timestamp)
        matches = [base_url + url
                   for url in url_links(base_url, regex=self.build_regex)]
        matches.sort()
        return matches[-1]  # the most recent build url

    def get_repo_name(self, date):
        return "mozilla-inbound"


class InboundRunner(NightlyRunner):

    def __init__(self, addons=None, appname="firefox", repo_name=None,
                 profile=None, cmdargs=[], bits=mozinfo.bits, persist=None):
        if appname == 'firefox':
            self.app = FirefoxInbound(bits=bits, persist=persist)
        elif appname == 'b2g':
            self.app = B2GInbound(bits=bits, persist=persist)
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
    parser.add_option("-a", "--addon", dest="addons",
                      help="an addon to install; repeat for multiple addons",
                      metavar="PATH1", default=[], action="append")
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
    runner = InboundRunner(addons=options.addons, profile=options.profile,
                           bits=options.bits, persist=options.persist)
    runner.start(get_date(options.date))
    try:
        runner.wait()
    except KeyboardInterrupt:
        runner.stop()

if __name__ == "__main__":
    cli()
