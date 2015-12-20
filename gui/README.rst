mozregression-gui
=================

This directory contains the code for mozregression-gui. It is a graphical
Qt application with the `PyQt4 bindings`_.

It is intended to be delivered as an executable (or a set of libs/binaries)
with cx_Freeze_.

.. _PyQt4 bindings: http://www.riverbankcomputing.com/software/pyqt/intro
.. _cx_Freeze: http://cx-freeze.readthedocs.org/en/latest/index.html


How to develop on mozregression-gui
-----------------------------------

There is an helper script **build.py** that is provided for distribution
tasks (as some replacement for the standard setup.py).

First thing is to install pyqt4. This must be done system wide (PyQT4
is not installable via pip).

- On Ubuntu: ::

    sudo apt-get install python-qt4 pyqt4-dev-tools

- On Archlinux: ::

    sudo pacman -S python2-pyqt4

- On OSX (using MacPorts_): ::

    sudo port install py27-pyqt4

- On OSX (using Homebrew_): ::

    Install qt and pyqt using brew

      brew install pyqt

    Install qt-creater for creating ui files

      brew install caskroom/cask/brew-cask
      brew cask install qt-creator

    Create Symbolic link to the Applications folder(optional)

      sudo ln -s /opt/homebrew-cask/Caskroom/qt-creator/3.4.0/Qt\ Creator.app/ /Applications/Qt\ Creator.app

    Configure qt-creator

      Launch qt-creator and open preferences
      Select Build & Run on the left and Qt Versions on the right
      Add Qt Version
      Search by typing cmd + shift + g and path /usr/local/qt/(qt-version)/qmake

.. _MacPorts: http://www.macports.org
.. _Homebrew: http://brew.sh

- On windows, you can download a pre build intaller from
  http://www.riverbankcomputing.co.uk/software/pyqt/download. Be careful to choose
  the qt4 / python 2.7 version for your architecture.


Next thing to do is to install the other dependencies. It is highly suggested to use
a virtualenv here, just be sure to pass the *-\-system-site-packages* flag
when you create it to be able to use the system-wide pyqt4. See this link
(http://docs.python-guide.org/en/latest/dev/virtualenvs/) to learn more
about python virtualenvs. You should also consider using virtualenvwrapper
(https://virtualenvwrapper.readthedocs.org/en/latest/).

Install with virtualenvwrapper: ::

   mkvirtualenv --system-site-packages -p /usr/bin/python2 mozregression
   pip install -r requirements-gui-dev.txt

Or with virtualenv: ::

   virtualenv --system-site-packages -p /usr/bin/python2 venv
   source venv/bin/activate
   pip install -r requirements-gui-dev.txt


Launching the application
-------------------------

Activate your virtualenv. On Linux or OSX: ::

  source venv/bin/activate
  # or 'workon mozregression' if you use virtualenvwrapper

Then simply run: ::

  python gui/build.py run


Running unit tests
------------------

Be sure to be in you virtualenv, then: ::

  python check.py -G

You can run them with coverage: ::

  python check.py -GCH
  firefox htmlcov/index.html


Freeze the application
----------------------

To generate one big file that contains everything int it: ::

  python gui/build.py bundle

The resulting file is in dist/. This file can be distributed to users
that have the same OS and arch as you (python is included in the file).
