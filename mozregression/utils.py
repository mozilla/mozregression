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