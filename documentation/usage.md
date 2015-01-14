---
layout: documentation
title: Usage
order: 20
---

# Usage of mozregression

Some useful command line usage.


## Testing application options

- Run for another application than firefox

       mozregression --app thunderbird

- Run with specific profile

       mozregression --profile=/path/to/profile

- Install addons

       mozregression --addon /path/to/addon --addon /other/addon

-  Forward arguments to tested binary

       mozregression --arg -foreground --arg -P

- Test a 32 bit binary on 64 bit system

       mozregression --bits 32

## Bisecting options

- Bisecting from specific nightly project branch

       mozregression  --repo mozilla-aurora

- Bisecting inbound directly

       mozregression --inbound --good-rev 8850aa0f --bad-rev 2a193b7f

- Look for a bug fix instead of a regression (bisect the other way around)

        mozregression --find-fix


## Network persistence

- Use a folder to keep downloaded files

        mozregression --persist temp

- Use a cache for http transfer (speeds up downloading the same builds a second time)

       mozregression --http-cache-dir cache


## Increase verbosity of mozregression

- Useful to understand what happens under the hood

       mozregression --log-mach-level debug
