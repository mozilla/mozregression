import sys
import mozinfo
from mozlog.structured import get_default_logger

from mozregression.runnightly import FennecNightly, FirefoxNightly, \
    B2GNightly, NightlyRunner
from mozregression.inboundfinder import FirefoxBuildsFinder, \
    FennecBuildsFinder, B2GBuildsFinder
from mozregression.utils import url_links, parse_date, parse_bits


def inbound_factory(klass, finder_klass):
    def __init__(self, bits=mozinfo.bits, persist=None, inbound_branch=None):
        if not inbound_branch:
            inbound_branch = finder_klass.default_inbound_branch
        klass.__init__(self, bits=bits,
                             persist=persist,
                             inbound_branch=inbound_branch)
        self.build_finder = finder_klass(bits=bits,
                                         inbound_branch=inbound_branch)

    def get_build_url(self, timestamp):
        base_url = "%s%s/" % (self.build_finder.build_base_url, timestamp)
        matches = [base_url + url
                   for url in url_links(base_url, regex=self.build_regex)]
        matches.sort()
        return matches[-1]  # the most recent build url

    def get_inbound_branch(self, date):
        return self.build_finder.default_inbound_branch

    return type(klass.__name__.replace('Nightly', 'Inbound'),
                (klass,),
                dict(__init__=__init__,
                     get_build_url=get_build_url,
                     get_inbound_branch=get_inbound_branch))


FirefoxInbound = inbound_factory(FirefoxNightly, FirefoxBuildsFinder)


FennecInbound = inbound_factory(FennecNightly, FennecBuildsFinder)


B2GInbound = inbound_factory(B2GNightly, B2GBuildsFinder)


class InboundRunner(NightlyRunner):

    def __init__(self, addons=None, appname="firefox", repo_name=None,
                 profile=None, cmdargs=[], bits=mozinfo.bits, persist=None,
                 inbound_branch=None):
        if appname == 'firefox':
            self.app = FirefoxInbound(bits=bits, persist=persist,
                                      inbound_branch=inbound_branch)
        elif appname == 'b2g':
            self.app = B2GInbound(bits=bits, persist=persist,
                                  inbound_branch=inbound_branch)
        else:
            self.app = FennecInbound(persist=persist,
                                     inbound_branch=inbound_branch)
        self.app_name = appname
        self.bits = bits
        self.addons = addons
        self.profile = profile
        self.persist = persist
        self.inbound_branch = self.app.inbound_branch
        self.cmdargs = list(cmdargs)
        self._logger = get_default_logger('Regression Runner')

    def print_resume_info(self, last_good_revision, first_bad_revision):
        self._logger.info('mozregression --good-rev=%s --bad-rev=%s%s'
                          % (last_good_revision,
                             first_bad_revision,
                             self.get_resume_options()))


def cli(args=sys.argv[1:]):
    from optparse import OptionParser
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
    parser.add_option("--inbound-branch", dest="inbound_branch",
                      help="inbound branch name on ftp.mozilla.org",
                      metavar="[tracemonkey|mozilla-1.9.2]", default=None)

    options, args = parser.parse_args(args)
    if not options.timestamp:
        sys.exit("timestamp must be specified")
    options.bits = parse_bits(options.bits)
    runner = InboundRunner(addons=options.addons, profile=options.profile,
                           bits=options.bits, persist=options.persist,
                           inbound_branch=options.inbound_branch)
    runner.start(parse_date(options.date))
    try:
        runner.wait()
    except KeyboardInterrupt:
        runner.stop()

if __name__ == "__main__":
    cli()
