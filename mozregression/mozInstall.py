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
# Clint Talbert.
# Portions created by the Initial Developer are Copyright (C) 2007
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#  Clint Talbert <ctalbert@mozilla.com>
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

from optparse import OptionParser
import platform
import subprocess
import re
import time
import string
import os
import shutil
import zipfile

from mozfile import rmtree

isDMG = re.compile(".*\.dmg")
isTARBZ = re.compile(".*\.tar\.bz")
isTARGZ = re.compile(".*\.tar\.gz")
isZIP = re.compile(".*\.zip")
isEXE = re.compile(".*\.exe")
_mozInstall_debug = False

def debug(s):
  if _mozInstall_debug:
    print "DEBUG: " + s

cygwinmatch = re.compile(".*cygwin.*", re.I)

# Copied from mozilla/testing/release/minotaur/getOSInfo.py - want this class
# to be self-sufficient without requiring another "non-standard" python lib,
# so duplicated this function from there.
def getPlatform():
  # On Vista, python reports "Microsoft" and on cygwin shells it can report
  # several different strings that contain the word "cygwin"
  if platform.system() == "Microsoft" or cygwinmatch.search(platform.system()):
    return "Windows"
  else:
    return platform.system()

class MozUninstaller:
  def __init__(self, **kwargs):
    debug("uninstall constructor")
    assert (kwargs['dest'] != "" and kwargs['dest'] != None)
    assert (kwargs['productName'] != "" and kwargs['productName'] != None)
    assert (kwargs['branch'] != "" and kwargs['dest'] != None)
    self.dest = kwargs['dest']
    self.productName = kwargs['productName']
    self.branch = kwargs['branch']

    # Handle the case where we haven't installed yet
    if not os.path.exists(self.dest):
      return

    if getPlatform() == "Windows":
      try:
        self.doWindowsUninstall()
      except:
        debug("Windows Uninstall threw - not overly urgent or worrisome")
    if os.path.exists(self.dest):
      try:
        os.rmdir(self.dest)
      except OSError:
        # Directories are still there - kill them all!
        rmtree(self.dest)

  def doWindowsUninstall(self):
    debug("do windowsUninstall")
    if self.branch == "1.8.0":
      uninstexe = self.dest + "/uninstall/uninstall.exe"
      uninstini = self.dest + "/uninstall/uninstall.ini"
      debug("uninstexe: " + uninstexe)
      debug("uninstini: " + uninstini)
      if os.path.exists(uninstexe):
        # modify uninstall.ini to run silently
        debug("modifying uninstall.ini")
        args = "sed -i.bak 's/Run Mode=Normal/Run Mode=Silent/' " + uninstini
        proc = subprocess.Popen(args, shell=True)
        # Todo handle error
        proc.wait()
        proc = subprocess.Popen(uninstexe, shell=True)
        proc.wait()
    elif self.branch == "1.8.1" or self.branch == "1.8" or self.branch == "1.9":
      debug("we are in 1.8 uninstall land")
      uninst = self.dest + "/uninstall/uninst.exe"
      helper = self.dest + "/uninstall/helper.exe"
      debug("uninst: " + uninst)
      debug("helper: " + helper)

      if os.path.exists(helper):
        debug("helper exists")
        args = helper + " /S /D=" + os.path.normpath(self.dest)
        debug("running helper with args: " + args)
        proc = subprocess.Popen(args, shell=True)
        proc.wait()
      elif os.path.exists(uninst):
        args = uninst + " /S /D=" + os.path.normpath(self.dest)
        debug("running uninst with args: " + args)
        proc = subprocess.Popen(args, shell=True)
        proc.wait()
      else:
        uninst = self.dest + "/" + self.product + "/uninstall/uninstaller.exe"
        args = uninst + " /S /D=" + os.path.normpath(self.dest)
        debug("running uninstaller with args: " + args)
        proc = subprocess.Popen(args, shell=True)
        proc.wait()
    time.sleep(10)

class MozInstaller:
  def __init__(self, **kwargs):
    debug("install constructor!")
    assert (kwargs['dest'] != "" and kwargs['dest'] != None)
    assert (kwargs['src'] != "" and kwargs['src'] != None)
    #assert (kwargs['productName'] != "" and kwargs['productName'] != None)
    #assert (kwargs['branch'] != "" and kwargs['branch'] != None)
    self.src = kwargs['src']
    self.dest = kwargs['dest']
    self.dest_app = kwargs['dest_app']
    #self.productName = kwargs['productName']
    #self.branch = kwargs['branch']
    #debug("running uninstall")
    #uninstaller = MozUninstaller(dest = self.dest, productName = self.productName,
     #                            branch = self.branch)

    if isDMG.match(self.src):
      self.installDmg(self.dest_app)
    elif isTARBZ.match(self.src):
      self.installTarBz()
    elif isTARGZ.match(self.src):
      self.installTarGz()
    elif isZIP.match(self.src):
      self.installZip()
    elif isEXE.match(self.src):
      self.installExe()

  # Simple utility function to get around python's path module's inability
  # to understand ~/... style paths
  def normalizePath(self, path):
    if path[0] == "~":
      path = os.path.expanduser(path)

    debug("NORMALIZE: path: " + path)

    try:
      if not os.path.exists(path):
        os.makedirs(path)
    except:
      # TODO: Better catch and error message
      print "Error creating destination directory " + path
    return path

  def installDmg(self, dest_app):
    # Ensure our destination directory exists
    self.dest = self.normalizePath(self.dest)

    # undmg code from Jesse
    mountpoint = os.path.join(self.dest, "MOUNTEDDMG")
    devnull = open(os.devnull, "w")
    subprocess.check_call(["hdiutil", "attach", "-quiet", "-mountpoint", mountpoint, self.src], stdout=devnull)

    app = 'Minefield.app'
    for fname in os.listdir(mountpoint):
      if fname.find(".app") != -1:
        app = fname

    try:
      #while not os.path.exists(mountpoint + "/MinefieldDebug.app"):
      #  print "waiting for disk image"
      #  time.sleep(1)
      shutil.copytree(os.path.join(mountpoint, app), os.path.join(self.dest, dest_app or app))
    finally:
      subprocess.check_call(["hdiutil", "detach", mountpoint], stdout=devnull)
      #shutil.rmtree(mountpoint)

  def installTarBz(self):
    # Ensure our destination directory exists
    self.dest = self.normalizePath(self.dest)
    self.unTar("-jxf")

  def installTarGz(self):
    # Ensure our destination directory exists
    self.dest = self.normalizePath(self.dest)
    self.unTar("-zxf")

  def unTar(self, tarArgs):
    args = "tar " + tarArgs + " " + self.src + " -C " + self.dest
    proc = subprocess.Popen(args, shell=True)
    proc.wait()
    #TODO: throw stderr

  def installZip(self):
    self.dest = self.normalizePath(self.dest)
    #TODO: throw stderr
    zipped = zipfile.ZipFile(self.src)
    try:
        zipped.extractall(self.dest)
    except:
        args = ["unzip", "-o", "-q", "-d", self.dest, self.src]
        proc = subprocess.Popen(args)
        proc.wait()
        
  def installExe(self):
    debug("running installEXE")
    args = self.src + " "
    if self.branch == "1.8.0":
      args += "-ms -hideBanner -dd " + self.dest
    else:
      debug("running install exe for 1.8.1")
      args += "/S /D=" + os.path.normpath(self.dest)
    # Do we need a shell=True here?
    proc = subprocess.Popen(args)
    proc.wait()
    # TODO: throw stderr

# Enable it to be called from the command line with the options
if __name__ == "__main__":
  parser = OptionParser()
  parser.add_option("-s", "--Source", dest="src",
                   help="Installation Source File (whatever was downloaded) -\
                         accepts Zip, Exe, Tar.Bz, Tar.Gz, and DMG",
                   metavar="SRC_FILE")
  parser.add_option("-d", "--Destination", dest="dest",
                    help="Directory to install the build into", metavar="DEST")
  parser.add_option("-b", "--Branch", dest="branch",
                    help="Branch the build is from must be one of: 1.8.0|1.8|\
                          1.9", metavar="BRANCH")
  parser.add_option("-p", "--Product", dest="product",
                    help="Product name - optional should be all lowercase if\
                         specified: firefox, fennec, thunderbird, etc",
                    metavar="PRODUCT")
  parser.add_option("-o", "--Operation", dest="op",
                    help="The operation you would like the script to perform.\
                         Should be either install (i) or uninstall (u) or delete\
                          (d) to recursively delete the directory specified in dest",
                    metavar="OP")

  (options, args) = parser.parse_args()

  # Run it
  if string.upper(options.op) == "INSTALL" or string.upper(options.op) == "I":
    installer = MozInstaller(src = options.src, dest = options.dest,
                             branch = options.branch, productName = options.product)
  elif string.upper(options.op) == "UNINSTALL" or string.upper(options.op) == "U":
    uninstaller = MozUninstaller(dest = options.dest, branch = options.branch,
                                 productName = options.product)
  elif string.upper(options.op) == "DELETE" or string.upper(options.op) == "D":
    rmtree(options.dest)
