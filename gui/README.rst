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


Then you need to compile the **Qt .ui files** (they describe some widgets)
into python files: ::

  python build.py uic

Note you will need to do that everytime a .ui file has changed. These .ui
files can be edited with the Qt **designer**. More information here:
http://wiki.qt.io/QtCreator_and_PySide.

Then simply run: ::

  python mozregression-gui.py


Freeze the application
----------------------

To generate one big file that contains everything int it: ::

  python build.py bundle

The resulting file is in dist/. This file can be distributed to users
that have the same OS and arch as you (python is included in the file).
