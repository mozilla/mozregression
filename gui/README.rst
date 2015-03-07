mozregression-gui
=================

This directory contains the code for mozregression-gui. It is a graphical
Qt application with the PySide bindings (http://pyside.github.io/docs/pyside/).

It is intended to be delivered as an executable (or a set of libs/binaries)
with pyinstaller (https://github.com/pyinstaller/pyinstaller).


How to develop on mozregression-gui
-----------------------------------

There is an helper script **build.py** that is provided for distribution
tasks (as some replacement for the standard setup.py).

So, first you may want to create a virtual env with everything in there: ::

  python build.py venv

This will create a **venv** dir, and install the dependencies inside.


Launching the application
-------------------------

Activate your environment. On linux: ::

  . venv/bin/activate

Then simply run: ::

  python build.py run


Running unit tests
------------------

Be sure to be in you virtual env, then: ::

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
