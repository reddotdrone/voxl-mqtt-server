#!/bin/bash
set -euo pipefail
case "${1:-native}" in
    native|qrb5165|qrb5165-2|arm64) ;;
    *) echo 'Usage: ./build.sh [native|qrb5165|qrb5165-2|arm64]' >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || exit 2
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$repo_dir/install_build_deps.sh" --check
exec "$repo_dir/make_package.sh"
