#!/usr/bin/env bash

set -e

LINTER_FILES="$(dirname "$0")/../.linter-files"

cat $LINTER_FILES | xargs isort --check-only
cat $LINTER_FILES | xargs flake8
