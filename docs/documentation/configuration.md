---
layout: documentation
title: Configuration file
doc_order: 1
description: How to preset options for mozregression
---

## Configuration file
To preset options into mozregression, create a configuration file (.INI formatted).
The recommended way to create a configuration file is to use the **-\-write-config**
command line flag. Then if you want some more customization, edit the file with
your text editor.

Location:

    $HOME/.mozilla/mozregression/mozregression.cfg

## Options available
Each option correspond to its command-line counter part (the long form,
but without the first double dashes, -\-). They are described [here](usage.html).

There is an exception for `--arg` which can be set in `mozregression.cfg` by using `cmdargs`.
For example, to pass a URL at which Firefox will open use
```
cmdargs = "https://mozilla.org",
```
Note the trailing comma, it is required to be correctly parsed as a list.

## Example

{% highlight ini %}
persist = /home/jp/.mozilla/mozregression/persist
persist-size-limit = 3.0
bits = 64
profile-persistence = clone-first
http-timeout = 30.0
enable-telemetry = yes
{% endhighlight %}
