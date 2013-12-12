from utils import urlLinks, strsplit, get_date
import re
import sys
from runnightly import FennecNightly, FirefoxNightly, NightlyRunner, parseBits
from inboundfinder import getBuildBaseURL
import mozinfo
from optparse import OptionParser

class FirefoxInbound(FirefoxNightly):

    repo_name = None

    def __init__(self, bits=mozinfo.bits, persist=None):
        self.persist = persist
        self.buildRegex = self._getBuildRegex(bits)
        self.bits = bits

    def getBuildUrl(self, timestamp):
        url = "%s%s/" % (getBuildBaseURL(self.bits), timestamp)
        for link in urlLinks(url):
            href = link.get("href")
            if re.match(self.buildRegex, href):
                return url + href

    def getRepoName(self, date):
        return "mozilla-inbound"

class FennecInbound(FennecNightly):

    repo_name = None

    def __init__(self, persist=None):
        self.persist = persist

    def getBuildUrl(self, timestamp):
        url = "%s%s/" % (getBuildBaseURL(appName=self.appName), timestamp)
        for link in urlLinks(url):
            href = link.get("href")
            if re.match(self.buildRegex, href):
                return url + href

    def getRepoName(self, date):
        return "mozilla-inbound"

class InboundRunner(NightlyRunner):

    def __init__(self, addons=None, appname="firefox", repo_name=None,
                 profile=None, cmdargs=(), bits=mozinfo.bits, persist=None):
        if appname == 'firefox':
            self.app = FirefoxInbound(bits=bits, persist=persist)
        else:
            self.app = FennecInbound(persist=persist)
        self.appName = appname
        self.bits = bits
        self.addons = addons
        self.profile = profile
        self.persist = persist
        self.cmdargs = list(cmdargs)

def cli(args=sys.argv[1:]):

    parser = OptionParser()
    parser.add_option("--timestamp", dest="timestamp", help="timestamp of "
                      "inbound build")
    parser.add_option("-a", "--addons", dest="addons",
                      help="list of addons to install",
                      metavar="PATH1,PATH2")
    parser.add_option("-p", "--profile", dest="profile", help="path to profile to user", metavar="PATH")
    parser.add_option("--bits", dest="bits", help="force 32 or 64 bit version (only applies to x86_64 boxes)",
                      choices=("32","64"), default=mozinfo.bits)
    parser.add_option("--persist", dest="persist", help="the directory in which files are to persist ie. /Users/someuser/Documents")

    options, args = parser.parse_args(args)
    if not options.timestamp:
        print "timestamp must be specified"
        sys.exit(1)
    options.bits = parseBits(options.bits)
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
