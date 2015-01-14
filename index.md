---
layout: default
title: Home
order: 0
main_link: True
---

# About mozregression

mozregression is an interactive regression range finder for Mozilla *nightly*
and *inbound* builds. It uses a binary search algorithm for quickly determining
a changeset range corresponding to when a problem was introduced. It is widely
used by Mozilla developers and other community members to help find regressions.

Currently, mozregression can works with:

- **firefox** (the default)
- **thunderbird**
- **fennec**
- **B2G**

To get a feel for how mozregression works, you can see the (pretty old but still
useful) video on
[codefirefox.com](http://codefirefox.com/video/mozregression), or take a look at
the [quick start]({{ "/quickstart.html" | prepend: site.baseurl }}) section.
