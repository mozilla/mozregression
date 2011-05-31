# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Mozilla Corporation Code.
#
# The Initial Developer of the Original Code is
# Heather Arthur
# Portions created by the Initial Developer are Copyright (C) 2009
# the Initial Developer. All Rights Reserved.
#
# Contributor(s): Heather Arthur <fayearthur@gmail.com>
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****
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
    strlist = string.split(sep)
    if len(strlist) == 1 and strlist[0] == '': # python's split function is ridiculous
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
