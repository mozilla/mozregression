# mozregression

mozregression is an interactive regression rangefinder for quickly tracking down the source of bugs in Mozilla nightly and inbound builds.

You can start using mozregression today:
- [start with our installation guide](https://mozilla.github.io/mozregression/install.html), then 
- take a look at [our Quick Start document](https://mozilla.github.io/mozregression/quickstart.html). 

## Status

[![Latest Version](https://img.shields.io/pypi/v/mozregression.svg)](https://pypi.python.org/pypi/mozregression/)
[![License](https://img.shields.io/pypi/l/mozregression.svg)](https://pypi.python.org/pypi/mozregression/)


Build status:
 - Linux:
   [![Linux Build Status](https://travis-ci.org/mozilla/mozregression.svg?branch=master)](https://travis-ci.org/mozilla/mozregression)
   [![Coverage Status](https://img.shields.io/coveralls/mozilla/mozregression.svg)](https://coveralls.io/r/mozilla/mozregression)
 - Windows: [![Windows Build status](https://ci.appveyor.com/api/projects/status/ukv1ariar1jboxar/branch/master?svg=true)](https://ci.appveyor.com/project/parkouss/mozregression/branch/master)

For more information see:

https://mozilla.github.io/mozregression/

## Building And Developing mozregression

Want to hack on mozregression ? Cool!

### Full environment setup

For a full environment setup (with GUI support), please see the [gui/README.rst file](gui/README.rst).
This is recommended.

### Command line only

If you are **really sure** that you only want to hack on the mozregression command line:

1. Install [virtualenv](https://virtualenv.pypa.io/en/stable/)
  or [virtualenvwrapper](https://virtualenvwrapper.readthedocs.org/en/latest/).

2. install dependencies:

  With virtualenvwrapper:

  ```bash
  mkvirtualenv -p /usr/bin/python2 mozregression
  pip install -r requirements-dev.txt
  ```

  Or with virtualenv: ::

  ```bash
  virtualenv -p /usr/bin/python2 venv
  source venv/bin/activate
  pip install -r requirements-dev.txt
  ```

3. run tests (be sure that your virtualenv is activated):

  ```bash
  ./check.py
  # or, with coverage support:
  ./check.py -CH
  ```
