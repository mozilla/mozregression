---
layout: documentation
title: Automatic bisection
doc_order: 10
description: How to evaluate tested build automatically with a command line
---

# Automatic bisection

As an alternative to using mozregression's interactive mode, it is possible
to evaluate builds automatically by writing a custom script. This can save
a lot of time if the reproduction steps are complicated or you have a large
regression range.


## The -\-command option

The -\-command option is used to evaluate builds automatically. It
takes as argument the command line that must be used to test the builds.
A return value of **0 will indicate a good build**, and
**any other return code will indicate a bad build**.


## Build variables

You can use variables in two ways:

- As placeholders in the command line

       --command 'my-test-command {binary}'

  Note that you must enclose variable names within curly brackets,
  **{}**.

- Using environment variables inside you command. In this case, variable
  names are upcased and prepended with **MOZREGRESSION_**. For example,
  **MOZREGRESSION_BINARY**.

This is the full list of available variables:

- **app_name**

  name of the application (one of {{ site.data.mozregression_supported_apps | map: "name" | join: ', ' }})

- **binary**

  path to the binary when applicable (**not for fennec**)

- **build_type**

  origin of the build, either 'nightly' or 'inbound'

- **build_url**

  url used to download the build

- **repository**

  mercurial repository of the build

- **changeset**

  mercurial changeset of the build

- **build_date**

  date of the build, using dd-mm-yyyy format (only for **nightly**)

- **timestamp**

  timestamp of the build (only for **inbound**)


## Test case with mozmill

Suppose that we know there is a regression between 2014-12-03 and 2015-01-10,
and that we know that the following
[mozmill script](http://hg.mozilla.org/qa/mozmill-tests/file/92fda125facf/firefox/tests/functional/restartTests/testMenu_quitApplication/test1.js)
can detect it (If you don't know **mozmill**, see
[here](https://developer.mozilla.org/en-US/docs/Mozilla/Projects/Mozmill)).

Well, we just have to run mozmill with the script on each build that
mozregression gives. Here are all the steps required to run the test case:

1. Install mozmill

       pip install mozmill

2. get the helpful mozmill script (or write it).

3. Run it in mozregression

       mozregression --good 2014-12-03 --bad 2015-01-10 \
       --command 'mozmill --binary {binary} -t test1.js'

   Note that 'test1.js' is he name of our mozmill script here.
