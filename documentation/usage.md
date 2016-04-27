---
layout: documentation
title: Usage
doc_order: 0
description: Some common command line options
---

# Usage of mozregression

Some useful command line usage. See **mozregression -\-help** for a complete and up
to date list of available options.


## Testing application options

- Run for another application than firefox

        mozregression --app thunderbird

- Run with specific profile

        mozregression --profile=/path/to/profile

 - Reuse a profile across tested builds

        mozregression --profile /path/to/profile --profile-persistence clone-first

- Install addons

        mozregression --addon /path/to/addon --addon /other/addon

-  Forward arguments to tested binary (note that you must use '=' for arguments beginning with '-' so that the     parser doesn't get confused)

        mozregression --arg='-foreground' --arg='-P'

   You can also use this option to point Firefox to a specific URL when loading:

        mozregression --arg="https://google.com"

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

        mozregression --good 33 --bad 34

- Bisecting from a specific project branch

        mozregression  --repo mozilla-aurora

- Bisecting inbound directly

        mozregression --good 8850aa0f --bad 2a193b7f

- Look for a bug fix instead of a regression (bisect the other way around)

        mozregression --find-fix

- Automate mozregression run (see [Automatic bisection]({{"/documentation/automatic-bisection.html" | prepend: site.baseurl}}))

        mozregression --command 'test-command {binary}'

## Network persistence

- Use a folder to keep downloaded files

        mozregression --persist temp

- Limit the size of the persist folder:

        mozregression --persist-size-limit

  Note that those options should be defined in the [configuration file](configuration.html).

- Keep downloading files in background

  When download in background is enabled (the default), the background download that
  is not used for testing is canceled. If you use the persist option and want to force
  the full download of these files (to be able to use them later), then you can keep
  these files by specifying a background download policy of keep:

        mozregression --persist tmp/ --background-dl-policy keep

## Increase verbosity

- Print the tested binaries outputs

        mozregression -P stdout

  Use the value *none* to disable.

- Useful to understand what happens under the hood

        mozregression --log-mach-level debug

## Miscellaneous

- List all command line options

        mozregression --help

- Show the current version

        mozregression --version

- List firefox releases numbers

        mozregression --list-releases
