mozregression-gui
=================

This directory contains the code for mozregression-gui. It is a graphical
Qt application with the `PySide2 bindings`_.

It is intended to be delivered as an executable (or a set of libs/binaries)
with PyInstaller_.

.. _PySide2 bindings: https://pypi.org/project/PySide2/
.. _PyInstaller: https://www.pyinstaller.org/


How to develop on mozregression-gui
-----------------------------------

There is an helper script **build.py** that is provided for distribution
tasks (as some replacement for the standard setup.py).

The first step is to install the dependencies. It is highly suggested to use
a virtualenv here. See this link
(http://docs.python-guide.org/en/latest/dev/virtualenvs/) to learn more
about python virtualenvs. You may also consider using virtualenvwrapper
(https://virtualenvwrapper.readthedocs.org/en/latest/).

Python 3.6+ is *required* to develop or use mozregression-gui.

Install with virtualenvwrapper: ::

   mkvirtualenv -p /usr/bin/python3 mozregression
   pip install -r requirements/all.txt
   pip install -e .

Or with virtualenv: ::

   virtualenv --system-site-packages -p /usr/bin/python3 venv
   source venv/bin/activate
   pip install -r requirements/all.txt
   pip install -e .

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

  python gui/build.py test


Freeze the application
----------------------

To generate one big file that contains everything int it: ::

  python gui/build.py bundle

The resulting file is in dist/. This file can be distributed to users
that have the same OS and arch as you (python is included in the file).
