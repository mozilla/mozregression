import re
import urllib2
import subprocess
from mozcommitbuilder import builder
from utils import urlLinks
import mozinfo
import sys
from optparse import OptionParser

def getBuildBaseURL(bits=mozinfo.bits):
    baseURL = 'http://inbound-archive.pub.build.mozilla.org/pub/mozilla.org/firefox/tinderbox-builds/'
    if mozinfo.os == "win":
        if bits == 64:
            # XXX this should actually throw an error to be consumed by the caller
            print "No builds available for 64 bit Windows"
            sys.exit()
        else:
            return baseURL + 'mozilla-inbound-win32/'
    elif mozinfo.os == "linux":
        if bits == 64:
            return baseURL + 'mozilla-inbound-linux64/'
        else:
            return baseURL + 'mozilla-inbound-linux/'
    elif mozinfo.os == "mac":
        return baseURL + 'mozilla-inbound-macosx64/'

def getInboundRevisions(startRev, endRev):
    commitBuilder = builder.Builder()

    revisions = map(lambda l: l.split()[0:2],
                    subprocess.check_output(['hg', 'log', '-R',
                                             commitBuilder.repoPath,
                                             '-r', '%s:%s' % (startRev,
                                                              endRev),
                                             '--template',
                                             '{node} {date|hgdate}\n']
                                            ).splitlines())

    start = (int(revisions[0][1]), revisions[0][0])
    end = (int(revisions[-1][1]), revisions[-1][0])
    rawRevisions = map(lambda l: l[0], revisions)

    baseURL = getBuildBaseURL()
    range = 60*60*4 # anything within four hours is potentially within the range
    timestamps = map(lambda l: int(l.get('href').strip('/')),
                     urlLinks(baseURL))
    timestampsInRange = filter(lambda t: t > (start[0] - range) and \
                             t < (end[0] + range), timestamps)
    revisions = [] # timestamp, order pairs
    for timestamp in timestampsInRange:
        for link in urlLinks("%s%s/" % (baseURL, timestamp)):
            href = link.get('href')
            if re.match('.*txt', href):
                url = "%s%s/%s" % (baseURL, timestamp, href)
                contents = urllib2.urlopen(url).read()
                remoteRevision = None
                for line in contents.splitlines():
                    parts = line.split('/rev/')
                    if len(parts) == 2:
                        remoteRevision = parts[1]
                        break
                if remoteRevision:
                    for (i, revision) in enumerate(rawRevisions):
                        if remoteRevision in revision:
                            revisions.append((revision, timestamp, i))

    # re-order timestamps (we want revision order, not build
    # order) and omit the first and last revisions, which we already
    # know about
    orderedRevisions = sorted(revisions, key=lambda r: r[2])
    return orderedRevisions[1:-2]

def getInboundTimestamps(startRev, endRev):
    revisions = getInboundRevisions(startRev, endRev)
    return map(lambda r: r[1], revisions)

def cli(args=sys.argv[1:]):

    parser = OptionParser()
    parser.add_option("--start-rev", dest="startRev", help="start revision")
    parser.add_option("--end-rev", dest="endRev", help="end revision")

    options, args = parser.parse_args(args)
    if not options.startRev or not options.endRev:
        print "start revision and end revision must be specified"
        sys.exit(1)

    revisions = getInboundRevisions(options.startRev, options.endRev)
    print "Revision, Timestamp, Order"
    for revision in revisions:
        print ", ".join(map(lambda s: str(s), revision))

if __name__ == "__main__":
    cli()
