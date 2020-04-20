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
- **Mac**:
  Download the latest **mozregression-gui.dmg** file from the
  [github releases]. Once the file is downloaded, click on it and drag
  the "mozregression GUI" icon to "Applications". Note that on recent
  versions of MacOS X you will need to [override the setting that disallows
  installing applications from unidentified developers](https://support.apple.com/en-ca/guide/mac-help/mh40616/mac) since at present we do not sign mozregression (see
  [bug 1366570]).

At present there is no version of the GUI for Linux, please see [bug 1581643]
for status on changing this.

## mozregression

The original command line tool, mozregression, is a Python (3.5+)
package installable via [pip]. You can find it on pypi, as
[mozregression](https://pypi.org/project/mozregression/)

[github releases]: https://github.com/mozilla/mozregression/releases
[bug 1366570]: https://bugzilla.mozilla.org/show_bug.cgi?id=1366570
[bug 1581643]: https://bugzilla.mozilla.org/show_bug.cgi?id=1581643
[pip]: https://pypi.org/project/pip/
