import re
import json
from utils import urlLinks
import mozinfo
import sys
from optparse import OptionParser

import requests

def getBuildBaseURL(appName='firefox', bits=mozinfo.bits):

    if appName == 'fennec':
        return "http://inbound-archive.pub.build.mozilla.org/pub/mozilla.org/mobile/tinderbox-builds/mozilla-inbound-android/"

    baseURL = 'http://inbound-archive.pub.build.mozilla.org/pub/mozilla.org/firefox/tinderbox-builds/'
    if mozinfo.os == "win":
        if bits == 64:
            # XXX this should actually throw an error to be consumed by the caller
            print "No builds available for 64 bit Windows (try specifying --bits=32)"
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

def getInboundRevisions(startRev, endRev, appName='firefox', bits=mozinfo.bits):

    revisions = []
    r = requests.get('https://hg.mozilla.org/integration/mozilla-inbound/'
                     'json-pushes?fromchange=%s&tochange=%s'% (startRev,
                                                               endRev))
    pushlog = json.loads(r.content)
    for pushid in sorted(pushlog.keys()):
        push = pushlog[pushid]
        revisions.append((push['changesets'][-1], push['date']))

    revisions.sort(key=lambda r: r[1])
    if not revisions:
        return []
    starttime = revisions[0][1]
    endtime = revisions[-1][1]
    rawRevisions = map(lambda l: l[0], revisions)

    baseURL = getBuildBaseURL(appName=appName, bits=bits)
    range = 60*60*4 # anything within four hours is potentially within the range
    timestamps = map(lambda l: int(l.get('href').strip('/')),
                     urlLinks(baseURL))
    timestampsInRange = filter(lambda t: t > (starttime - range) and
                               t < (endtime + range), timestamps)
    revisions = [] # timestamp, order pairs
    for timestamp in timestampsInRange:
        for link in urlLinks("%s%s/" % (baseURL, timestamp)):
            href = link.get('href')
            if re.match('^.+\.txt$', href):
                url = "%s%s/%s" % (baseURL, timestamp, href)
                response = requests.get(url)
                remoteRevision = None
                for line in response.iter_lines():
                    # Filter out Keep-Alive new lines.
                    if not line:
                        continue
                    parts = line.split('/rev/')
                    if len(parts) == 2:
                        remoteRevision = parts[1]
                        break # for line
                if remoteRevision:
                    for (i, revision) in enumerate(rawRevisions):
                        if remoteRevision in revision:
                            revisions.append((revision, timestamp, i))
                break # for link

    return sorted(revisions, key=lambda r: r[2])

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
