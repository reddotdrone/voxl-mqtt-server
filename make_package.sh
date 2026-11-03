#!/bin/bash
set -euo pipefail
[[ $# == 0 ]] || { echo 'Usage: ./make_package.sh' >&2; exit 2; }
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$repo_dir/tools/make_package.py"
