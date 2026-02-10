---
layout: default
title: Quick start
order: 10
main_link: True
---

# The Basics

With MozRegression, you are trying to find the first "bad" build, which refers to where
the regression first appears.

When provided with the option to determine the outcome of each test (that you conduct per
build):

- "Good" means that the test passed (the build works).

- "Bad" means that the test failed, so it exhibits the regression.

- "Broken" means that that build could not be tested, maybe because it doesn't run at all,
  or fails for an unrelated reason. That option allows you evaluate another build that is
  nearby (so-to-speak), without changing the bisect range.

# GUI

The easiest way to use mozregression (at least on Windows) is via the GUI. This
youtube video by Pascal Chevrel describes how to install and use it:

<center><iframe width="560" height="315" src="https://www.youtube.com/embed/IwrWot3jVFI" frameborder="0" allowfullscreen></iframe></center>

# Command line

The command-line version of mozregression is good for power users, or those using Linux,
or macOS.

Let's say that you just found a bug in the current nightly build, and you know that
that bug didn't exist in the nightly from a few weeks ago. You want to find the
regression range of this bug (the window of commits the bug was introduced in).

To find the range run the mozregression command on the command-line and give
it a known "good" date with the good argument:

    mozregression --good 2014-12-25

You can also specify the most distant known "bad" nightly date with the bad argument.

    mozregression --good 2014-12-25 --bad 2015-01-07

This will guide you through a bisection, automatically downloading and opening
nightly builds from various dates (on new, clean profiles) and asking you
whether the bug exists in them. After doing this a few times you'll get the
regression range, something like this: 

> Pushlog:
> https://hg.mozilla.org/mozilla-central/pushloghtml?fromchange=636498d041b5&tochange=2a193b7f395c

![My helpful screenshot]({{ site.baseurl }}/images/mozreg.png)

Then mozregression will go on and do the same things with integration builds
to get you the smallest possible window range.

There is plenty of options for mozregression. See

    mozregression -h

To list them all. Have a look at the
[documentation]({{ "/documentation/" | prepend: site.baseurl }})
section to learn more!
