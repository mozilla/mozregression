---
layout: documentation
title: Telemetry
doc_order: 100
description: About the use of Telemetry in mozregression
---

# Telemetry

Unless explicitly disabled, mozregression will send an anonymized telemetry ping (a small JSON-document) to Mozilla's servers on each use (command-line invocation in the case of console mozregression, each bisection or single run in the case of the GUI).

This data is anonymized and not personally identifiable, it contains only:

- A random client id (e.g. `5a26b9f7-c025-4858-abce-63ca73ceebf0`)
- Variant of mozregression application used (GUI, console, or the
  mach interface)
- Application used (e.g. Firefox or Thunderbird)
- Some very basic information on the environment in which mozregression
  is running (e.g. operating system)

The purpose of this data gathering is only to improve mozregression itself by understanding the scope of its environment and usage, and
will not be broadly shared except in aggregated form. Although not a consumer product, mozregression strives to follow Mozilla's general guidelines on [lean data practices](https://www.mozilla.org/en-US/about/policy/lean-data/).

## How to disable

We encourage you to leave Telemetry enabled -- if we know that people
are getting value out of mozregression, it provides an incentive to
make it better! That said, disabling mozregression is easy. In the
command-line variant, you can either pass `--disable-telemetry` in
the arguments, or set `enable-telemetry` to no inside your [configuration file](./configuration.md).
In the GUI version, simply untick the box "Enable Telemetry" in the preferences dialog (after clicking "Show Advanced Options").
