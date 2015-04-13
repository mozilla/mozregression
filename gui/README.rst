mozregression-gui
=================

This directory contains the code for mozregression-gui. It is a graphical
Qt application with the `PyQt4 bindings`_.

It is intended to be delivered as an executable (or a set of libs/binaries)
with pyinstaller_.

.. _PyQt4 bindings: http://www.riverbankcomputing.com/software/pyqt/intro
.. _pyinstaller: https://github.com/pyinstaller/pyinstaller


How to develop on mozregression-gui
-----------------------------------

There is an helper script **build.py** that is provided for distribution
tasks (as some replacement for the standard setup.py).

First thing is to install pyqt4. This must be done system wide (PyQT4
is not installable via pip).

- On ubuntu: ::

    sudo apt-get install python-qt4 pyqt4-dev-tools

- On OSX (using MacPorts_): ::

    sudo port install py27-pyqt4

- On OSX (using Homebrew_): ::

    brew install pyqt

.. _MacPorts: http://www.macports.org
.. _Homebrew: http://brew.sh

- On windows, you can download a pre build intaller from
  http://www.riverbankcomputing.co.uk/software/pyqt/download. Be careful to choose
  the qt4 / python 2.7 version for your architecture.


Next thing to do is to install the others dependencies. It is highly suggested to use
a virtualenv here, just be sure to pass the *-\-system-site-packages* flag
when you create it to be able to use the system-wide pyqt4. See this link
(http://docs.python-guide.org/en/latest/dev/virtualenvs/) to learn more
about python virtualenvs.


Launching the application
-------------------------

Activate your virtualenv. On Linux or OSX: ::

  . venv/bin/activate

Then simply run: ::

  python build.py run


Running unit tests
------------------

Be sure to be in you virtualenv, then: ::

  python build.py test

You can run them with coverage: ::

  pip install coverage
  coverage run build.py test
  coverage html
  firefox htmlcov/index.html


Freeze the application
----------------------

To generate one big file that contains everything int it: ::

  python build.py bundle

The resulting file is in dist/. This file can be distributed to users
that have the same OS and arch as you (python is included in the file).
