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
 - Windows: [![Windows Build status](https://ci.appveyor.com/api/projects/status/bcg7t1pt2bahggdr?svg=true)](https://ci.appveyor.com/project/wlach/mozregression/branch/master)

For more information see:

https://mozilla.github.io/mozregression/

## Issue Tracking

Found a bug in mozregression? We track issues [here](https://bugzilla.mozilla.org/buglist.cgi?quicksearch=product%3ATesting%20component%3Amozregression&list_id=14890897).
You can file a new bug [here](https://bugzilla.mozilla.org/enter_bug.cgi?product=Testing&component=mozregression).

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
  mkvirtualenv -p /usr/bin/python3 mozregression
  pip install -r requirements-dev.txt
  ```

  Or with virtualenv: ::

  ```bash
  virtualenv -p /usr/bin/python3 venv
  source venv/bin/activate
  pip install -r requirements-dev.txt
  ```

3. run tests (be sure that your virtualenv is activated):

  ```bash
  python setup.py test
  ```
