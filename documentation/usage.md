---
layout: documentation
title: Usage
doc_order: 0
description: Some common command line options
---

# Usage of mozregression

Some useful command line usage.


## Testing application options

- Run for another application than firefox

       mozregression --app thunderbird

- Run with specific profile

       mozregression --profile=/path/to/profile

- Install addons

       mozregression --addon /path/to/addon --addon /other/addon

-  Forward arguments to tested binary (note that you must use '=' for arguments beginning with '-' so that the     parser doesn't get confused)

       mozregression --arg='-foreground' --arg='-P'

- Test a 32 bit binary on 64 bit system

       mozregression --bits 32

  Note: On linux systems (particularly Ubuntu) if you are facing errors in running 32-bit Firefox on
  64-bit machine, the cause is often missing 32-bit libraries. Use --log-mach-level=debug along with the
  above command to figure out which library is needed. For example, if the browser is not launching and
  you get an error like:

       libXt.so.6: cannot open shared object file: No such file or directory

  You will need to install the library libXt6:i386 via 'sudo apt-get install libXt6:i386'. In case,
  you don't get a library needed error and some other error (like OSError) install the library
  libstdc++6:i386 via 'sudo apt-get install libstdc++6:i386' and try running mozregression again to see if
  a useful error comes up!

## Bisecting options

- Bisecting nightlies

       mozregression  --good 2014-12-25 --bad 2015-01-07

- Bisecting nightlies given firefox releases number

       mozregression --good-release 33 --bad-release 34

- Bisecting from a specific nightly project branch

       mozregression  --repo mozilla-aurora

- Bisecting inbound directly

       mozregression --good-rev 8850aa0f --bad-rev 2a193b7f

- Look for a bug fix instead of a regression (bisect the other way around)

        mozregression --find-fix

- Automate mozregression run (see [Automatic bisection]({{"/documentation/automatic-bisection.html" | prepend: site.baseurl}}))

       mozregression --command 'test-command {binary}'

## Network persistence

- Use a folder to keep downloaded files

        mozregression --persist temp

- Use a cache for http transfer (speeds up downloading the same builds a second time)

       mozregression --http-cache-dir cache


## Increase verbosity

- Useful to understand what happens under the hood

       mozregression --log-mach-level debug

## Miscellaneous

- List all command line options

       mozregression --help

- Show the current version

       mozregression --version

- List firefox releases numbers

       mozregression --list-releases
