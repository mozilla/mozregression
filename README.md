# mozregression

mozregression is an interactive regression rangefinder for quickly tracking down the source of bugs in Mozilla nightly and integration builds.

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

## Contact

You can chat with the mozregression developers on Mozilla's instance of [Matrix](https://chat.mozilla.org/#/room/#mozregression:mozilla.org): https://chat.mozilla.org/#/room/#mozregression:mozilla.org

## Issue Tracking

Found a problem with mozregression? Have a feature request? We track bugs [on bugzilla](https://bugzilla.mozilla.org/buglist.cgi?quicksearch=product%3ATesting%20component%3Amozregression&list_id=14890897).
You can file a new bug [here](https://bugzilla.mozilla.org/enter_bug.cgi?product=Testing&component=mozregression).

## Building And Developing mozregression

Want to hack on mozregression ? Cool!

### Installing dependencies

To make setup more deterministic, we have provided requirements files to use a known-working
set of python dependencies. From your mozregression checkout, you can install these inside
a virtual development environment.

After checking out the mozregression repository from GitHub, this is a two step process:

1. Be sure you are using Python 3.6 or above: earlier versions are not supported (if you
   are not sure, run `python --version` or `python3 --version` on the command line).

2. If you don't have it already, install [virtualenv](https://virtualenv.pypa.io/en/stable/).

3. From inside your mozregression checkout, create a virtualenv, activate it, and install the dependencies. The instructions are slightly different depending on whether you are using Windows or Linux/MacOS.

On Windows:

```bash
virtualenv -p python venv
venv\Scripts\activate
pip install -r requirements\build.txt -r requirements\linters.txt
pip install -e .
```

On Linux/MacOS:

```bash
virtualenv -p python3 venv
source venv/bin/activate
pip install -r requirements/build.txt -r requirements/linters.txt
pip install -e .
```

### Hacking on mozregression

After running the above commands, you should be able to run the command-line version of
mozregression as normal (e.g. `mozregression --help`) inside the virtual environment. If
you wish to try running the GUI, use the provided helper script:

```bash
python gui/build.py run
```

To run the unit tests for the console version:

```bash
pytest tests
```

For the GUI version:

```bash
python gui/build.py test
```

Before submitting a pull request, please lint your code for errors and formatting (we use [black](https://black.readthedocs.io/en/stable/), [flake8](https://flake8.pycqa.org/en/latest/) and [isort](https://isort.readthedocs.io/en/latest/))

```bash
./bin/lint-check.sh
```

If it turns up errors, try using the `lint-fix.sh` script to fix any errors which can be addressed automatically:

```bash
./bin/lint-fix.sh
```
