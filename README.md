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
  [![Coverage Status](https://img.shields.io/coveralls/mozilla/mozregression.svg)](https://coveralls.io/r/mozilla/mozregression)

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

1. Be sure you are using Python 3.8 or above: earlier versions are not supported (if you
   are not sure, run `python --version` or `python3 --version` on the command line).

2. From inside your mozregression checkout, create a virtual environment, activate it, and install the dependencies. The instructions are slightly different depending on whether you are using Windows or Linux/MacOS.


On Windows:

```bash
python3 -m venv venv
venv\Scripts\activate
pip install -r requirements\requirements-3.9-Windows.txt
pip install -e .
```

On Linux:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements/requirements-3.9-Linux.txt
pip install -e .
```

On macOS:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements/requirements-3.9-macOS.txt
pip install -e .
```

NOTE: You should replace the Python version with the one that matches with the virtual environment.

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

### Making a release

Create a new GitHub release and give it a tag name identical to the version number you want (e.g. `4.0.20`). CI should automatically upload new versions of the GUI applications to the release and to TestPyPI and PyPI.

Follow the following conventions for pre-releases:

- For development releases, tags should be appended with .devN, starting with N=0. For example, 6.2.1.dev0.
- For alpha, beta, or release candidates, tags should be appended with aN, bN, or rcN, starting with N=0. For example, 6.2.1a0.dev4, 6.2.1rc2, etc...

For more info, see [PEP 440](https://peps.python.org/pep-0440/).

#### Signing and notarizing macOS releases

Uploading the signed artifacts is a manual process at this time. To sign and notarize a macOS release, follow these steps:

- Copy the signing manifest output from the build job.
- Create a pull request to update `signing-manifests/mozregression-macOS.yml` in the [adhoc-signing](https://github.com/mozilla-releng/adhoc-signing) repo with those changes.
- Wait for pull request to be merged, and the signing task to finish.
- After the signing task is finished, download `mozregression-gui-app-bundle.tar.gz` and extract it in `gui/dist`.
- Run `./bin/dmgbuild`.
- Upload new dmg artifact (gui/dist/mozregression-gui.dmg) to the corresponding release.
