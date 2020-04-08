#!/bin/sh

# presumes glean SDK is installed and available in local path

glean_parser translate -f markdown -o docs/glean mozregression/metrics.yaml mozregression/pings.yaml
