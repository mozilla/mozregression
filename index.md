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

{% comment %}I am not able to write it with line breaks and keep good list formatting{% endcomment %}
{% for app in site.data.mozregression_supported_apps %}{% assign first = site.data.mozregression_supported_apps | first %}
- **[{{app.name}}]({{app.url}})**{% if app.description %} ({{app.description}}){% endif %}{% if app == first %} - default{% endif %}{% endfor %}

To get a feel for how mozregression works, you can see the (pretty old but still
useful) video on
[codefirefox.com](http://codefirefox.com/video/mozregression), or take a look at
the [quick start]({{ "/quickstart.html" | prepend: site.baseurl }}) section.
