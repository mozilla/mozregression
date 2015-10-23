---
layout: documentation
title: Configuration file
doc_order: 1
description: How to preset options for mozregression
---

## Configuration file
To preset options into mozregression, create a configuration file (.INI formatted).

Location:

    $HOME/.mozilla/mozregression/mozregression.cfg

## Options available
Each option correspond to its command-line counter part. They are described [here](usage.html).

- profile

- app

- repo

- inbound-branch

- bits

- persist

- http-timeout

- background-dl-policy

## Example

    persists=true
    bits=64
    app=fennec
    profile=PROFILE
    persist=~/mozpersist
    http-timeout=10.2
    repo="mozilla-aurora"
    background-dl-policy = keep
