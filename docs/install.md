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
  follow the installation process. Some anti-virus programs falsely claim that
  mozregression is a virus, you can ignore this warning: see [bug 1647533].
- **macOS**:
  Download the latest **mozregression-gui.dmg** file from the
  [github releases]. Once the file is downloaded, open it and drag
  the "mozregression GUI" icon to "Applications".
- **Linux**:
  Download the gzipped tarball of mozregression-gui corresponding to your
  version of Ubuntu from the [github releases]. Once the file is downloaded,
  extract it and run the `mozregression-gui` file in the `mozregression-gui`
  directory. Example:

  ```sh
  tar xf mozregression-gui-ubuntu-22.04.tar.gz
  mozregression-gui/mozregression-gui
  ```

## mozregression

The original command line tool, mozregression, is a Python
package installable via [pip]. You can find it on PyPI, as
[mozregression](https://pypi.org/project/mozregression/).

Note that you will need a reasonably current version of pip to install mozregression to be able to download the [Glean] dependency.
If you get any errors installing Glean and you have an older Python, try upgrading your local copy of pip ([Why you really need to upgrade pip] might be helpful for Linux users).

## mach

If you have an existing [Firefox source checkout], you can install and use
mozregression via [mach]. For example:

```sh
./mach mozregression --help
```

[github releases]: https://github.com/mozilla/mozregression/releases
[bug 1366570]: https://bugzilla.mozilla.org/show_bug.cgi?id=1366570
[bug 1581643]: https://bugzilla.mozilla.org/show_bug.cgi?id=1581643
[bug 1647533]: https://bugzilla.mozilla.org/show_bug.cgi?id=1647533
[pip]: https://pypi.org/project/pip/
[Glean]: https://mozilla.github.io/glean
[Why you really need to upgrade pip]: https://pythonspeed.com/articles/upgrade-pip/
[Firefox source checkout]: https://firefox-source-docs.mozilla.org/contributing/vcs/mercurial.html
[mach]: https://firefox-source-docs.mozilla.org/mach/index.html
