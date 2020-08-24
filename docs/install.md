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
- **Mac**:
  Download the latest **mozregression-gui.dmg** file from the
  [github releases]. Once the file is downloaded, click on it and drag
  the "mozregression GUI" icon to "Applications". Note that on recent
  versions of MacOS X you will need to [override the setting that disallows
  installing applications from unidentified developers](https://support.apple.com/en-ca/guide/mac-help/mh40616/mac) since at present we do not sign mozregression (see
  [bug 1366570]).
- **Linux**:
  Download the latest **mozregression-gui.tar.gz** file from the
  [github releases]. Once the file is downloaded, extract it and run the
  `mozregression-gui` file in the `mozregression-gui` directory. Example:

  ```sh
  tar xf mozregression-gui.tar.gz
  mozregression-gui/mozregression-gui
  ```

## mozregression

The original command line tool, mozregression, is a Python (3.6+)
package installable via [pip]. You can find it on pypi, as
[mozregression](https://pypi.org/project/mozregression/)

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
[Firefox source checkout]: https://firefox-source-docs.mozilla.org/contributing/vcs/mercurial.html
[mach]: https://firefox-source-docs.mozilla.org/mach/index.html
