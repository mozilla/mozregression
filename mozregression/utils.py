import re
import httplib2
import datetime
import platform

def current_platform():
    (bits, linkage) = platform.architecture()

    os = platform.system()
    if os == 'Microsoft' or os == 'Windows' or re.match(".*cygwin.*", os):
        return "Windows " + bits # 'Windows 32bit'
    elif os == 'Linux':
        return "Linux " + bits
    elif os == 'Darwin' or os == 'Mac':
        return "Mac " + bits

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