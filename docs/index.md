---
layout: home
title: Home
order: 0
main_link: True
---

# About mozregression

mozregression is an interactive regression range finder for Firefox and other Mozilla
products. It uses a binary search algorithm for quickly determining a changeset range
corresponding to when a problem was introduced.

Currently, mozregression can work with:

{% comment %}I am not able to write it with line breaks and keep good list formatting{% endcomment %}
{% for app in site.data.mozregression_supported_apps %}{% assign first = site.data.mozregression_supported_apps | first %}
- **[{{app.name}}]({{app.url}})**{% if app.description %} ({{app.description}}){% endif %}{% if app == first %} - default{% endif %}{% endfor %}

To get a feel for how mozregression works, see this video from Pascal Chevrel:

<center><iframe width="560" height="315" src="https://www.youtube.com/embed/IwrWot3jVFI" frameborder="0" allowfullscreen></iframe></center>
