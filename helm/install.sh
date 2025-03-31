#!/usr/bin/env bash

helm dependency update ./
helm upgrade --install archive-query-log ./ -n archive-query-log --create-namespace -f values.yaml -f values.override.yaml "$@"
