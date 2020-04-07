---
layout: documentation
title: Telemetry
doc_order: 100
description: About the use of Telemetry in mozregression
---

# Telemetry

Unless explicitly disabled, mozregression will send a telemetry "ping" (a small JSON-document) to Mozilla's servers on each use (command-line invocation in the case of console mozregression, each bisection or single run in the case of the GUI).

This ping does not contain any personally identifiable information and
is intentionally limited to what we need to understand the basics
of how mozregression is being used (for example, understanding
which applications are being bisected). For an up-to-date list of
what is being collected, please see this [automatically
generated report](https://github.com/mozilla/mozregression/blob/master/docs/glean/metrics.md).

The purpose of this data gathering is only to improve mozregression itself by understanding the scope of its environment and usage, and
will not be broadly shared except in aggregated form. Although not a consumer product, mozregression strives to follow Mozilla's general guidelines on [lean data practices](https://www.mozilla.org/en-US/about/policy/lean-data/) and is subject to our [privacy policy](https://www.mozilla.org/en-US/privacy/websites/).

## How to disable

We encourage you to leave Telemetry enabled -- if we know that people
are getting value out of mozregression, it provides an incentive to
make it better! That said, disabling mozregression is easy. In the
command-line variant, you can set `enable-telemetry` to no inside your [configuration file](./configuration.md). In the GUI version, simply untick the box "Enable Telemetry" in the preferences dialog (after clicking "Show Advanced Options").
