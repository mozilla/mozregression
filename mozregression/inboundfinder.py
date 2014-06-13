import re
import json
import mozinfo
import sys
from optparse import OptionParser
import requests

from mozregression.utils import url_links


def get_build_base_url(app_name='firefox', bits=mozinfo.bits, os=mozinfo.os):

    if app_name == 'fennec':
        return "http://inbound-archive.pub.build.mozilla.org/pub/mozilla.org" \
            "/mobile/tinderbox-builds/mozilla-inbound-android/"

    if app_name == 'b2g':
        base_url = 'http://ftp.mozilla.org/pub/mozilla.org/b2g'\
            '/tinderbox-builds/b2g-inbound-%s_gecko/'
    else:
        base_url = 'http://inbound-archive.pub.build.mozilla.org/pub' \
            '/mozilla.org/firefox/tinderbox-builds/mozilla-inbound-%s/'
    if os == "win":
        if bits == 64:
            # XXX this should actually throw an error to be consumed
            # by the caller
            print "No builds available for 64 bit Windows" \
                " (try specifying --bits=32)"
            sys.exit()
        else:
            return base_url % 'win32'
    elif os == "linux":
        if bits == 64:
            return base_url % 'linux64'
        else:
            return base_url % ('linux32' if app_name == 'b2g' else 'linux')
    elif os == "mac":
        return base_url % 'macosx64'


def get_inbound_revisions(start_rev, end_rev, app_name='firefox',
                          bits=mozinfo.bits, os=mozinfo.os):

    revisions = []
    url_part = 'b2g' if app_name == 'b2g' else 'mozilla'
    r = requests.get('https://hg.mozilla.org/integration/%s-inbound/'
                     'json-pushes?fromchange=%s&tochange=%s' % (url_part,
                                                                start_rev,
                                                                end_rev))
    pushlog = json.loads(r.content)
    for pushid in sorted(pushlog.keys()):
        push = pushlog[pushid]
        revisions.append((push['changesets'][-1], push['date']))

    revisions.sort(key=lambda r: r[1])
    if not revisions:
        return []
    starttime = revisions[0][1]
    endtime = revisions[-1][1]
    raw_revisions = map(lambda l: l[0], revisions)

    base_url = get_build_base_url(app_name=app_name, bits=bits, os=os)
    # anything within twelve hours is potentially within the range
    # (should be a tighter but some older builds have wrong timestamps,
    # see https://bugzilla.mozilla.org/show_bug.cgi?id=1018907 ...
    # we can change this at some point in the future, after those builds
    # expire)
    range = 60*60*12
    timestamps = map(lambda l: int(l),
                     # sometimes we have links like "latest"
                     filter(lambda l: l.isdigit(),
                            map(lambda l: l.get('href').strip('/'),
                                url_links(base_url))))
    timestamps_in_range = filter(lambda t: t > (starttime - range) and
                                 t < (endtime + range), timestamps)
    revisions = []  # timestamp, order pairs
    for timestamp in timestamps_in_range:
        for link in url_links("%s%s/" % (base_url, timestamp)):
            href = link.get('href')
            if re.match(r'^.+\.txt$', href):
                url = "%s%s/%s" % (base_url, timestamp, href)
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
                    for (i, revision) in enumerate(raw_revisions):
                        if remote_revision in revision:
                            revisions.append((revision, timestamp, i))
                break  # for link

    return sorted(revisions, key=lambda r: r[2])


def cli(args=sys.argv[1:]):

    parser = OptionParser()
    parser.add_option("--start-rev", dest="start_rev", help="start revision")
    parser.add_option("--end-rev", dest="end_rev", help="end revision")
    parser.add_option("--os", dest="os", help="override operating system "
                      "autodetection (mac, linux, win)", default=mozinfo.os)
    parser.add_option("--bits", dest="bits", help="override operating system "
                      "bits autodetection", default=mozinfo.bits)
    parser.add_option("-n", "--app", dest="app", help="application name "
                      "(firefox, fennec or thunderbird)",
                      metavar="[firefox|fennec|thunderbird]",
                      default="firefox")

    options, args = parser.parse_args(args)
    if not options.start_rev or not options.end_rev:
        print "start revision and end revision must be specified"
        sys.exit(1)

    revisions = get_inbound_revisions(options.start_rev, options.end_rev,
                                      app_name=options.app, os=options.os,
                                      bits=options.bits)
    print "Revision, Timestamp, Order"
    for revision in revisions:
        print ", ".join(map(lambda s: str(s), revision))

if __name__ == "__main__":
    cli()
