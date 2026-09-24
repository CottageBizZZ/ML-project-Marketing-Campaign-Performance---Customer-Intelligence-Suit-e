#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
for s in src/0{1,2,3,4,5,6}_*.py; do echo "== $s"; python "$s"; done
