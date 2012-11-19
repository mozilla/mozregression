# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import re
import httplib2
import datetime
import platform

def get_platform():
    uname = platform.uname()
    name = uname[0]
    version = uname[2]

    if name == "Linux":
        (distro, version, codename) = platform.linux_distribution()
        version = distro + " " + version
    elif name == "Darwin":
        name = "Mac"
        (release, versioninfo, machine) = platform.mac_ver()
        version = "OS X " + release
    elif name == "Microsoft":
        name = "Windows"

    bits = platform.architecture()[0]
    cpu = uname[4]
    if cpu == "i386" or cpu == "i686":
        if bits == "32bit":
            cpu = "x86"
        elif bits == "64bit":
            cpu = "x86_64"
    elif cpu == 'Power Macintosh':
        cpu = 'ppc'

    bits = re.compile('(\d+)bit').search(bits).group(1)

    return {'name': name, 'version': version, 'bits':  bits, 'cpu': cpu}


def strsplit(string, sep):
    # XXX https://github.com/mozilla/mozregression/issues/50
    strlist = string.split(sep)
    if strlist == ['']:
      return []
    return strlist

def download_url(url, dest=None):
    h = httplib2.Http()
    resp, content = h.request(url, "GET")
    if dest == None:
        dest = os.path.basename(url)

    local = open(dest, 'wb')
    local.write(content)
    local.close()
    return dest

def get_date(dateString):
    p = re.compile('(\d{4})\-(\d{1,2})\-(\d{1,2})')
    m = p.match(dateString)
    if not m:
        print "Incorrect date format"
        return
    return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

def increment_day(date):
    s = date.split("-")
    delta = datetime.timedelta(days=1)
    nextDate = datetime.date(int(s[0]),int(s[1]),int(s[2])) + delta
    return str(nextDate)
