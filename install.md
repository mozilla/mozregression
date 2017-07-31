---
layout: default
title: Install
order: 30
main_link: True
---

# Install or upgrade

## mozregression-gui

For the graphical interface, we provide a simple installation process:

- **Windows**:
  Download the latest **mozregression-gui.exe** file from the
  [github releases]. Once the file is downloaded double-click on it and
  follow the installation process.

- **Linux 64**:
  We provide a frozen application (that includes python itself) in the
  [github releases]. You can try it out by downloading the
  **mozregression-gui.tar.gz**, decompress it somewhere and run the
  mozregression-gui executable file.

## mozregression

The original command line tool.

mozregression is a Python (currently 2.7) package installable via pip. You can
follow the OS-specific instructions to install pip if you don't know how to do it:

- **Windows**

  Download and install python 2.7 from
  [ActiveState](http://www.activestate.com/activepython/downloads).
  It will include pip and set python in your PATH.
- **Mac**

      sudo easy_install pip

- **Ubuntu**

      sudo apt-get install python-pip

- **Other linuxes**

  *Beware! Some distributions use Python 3 by default. In this case you need to install python2-pip.*

  Example for archlinux:

      sudo pacman -S python2-pip

Once you have pip installed along with python 2.7, just open a terminal
(or a windows shell) and execute the following depending on what platform
you are on:

- **Windows**

      pip install -U mozregression

- **Linux / Mac**

      sudo pip2 install -U mozregression

[github releases]: https://github.com/mozilla/mozregression/releases
[from github]: https://github.com/mozilla/mozregression/blob/master/gui/README.rst
