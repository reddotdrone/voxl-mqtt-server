#!/bin/bash
set -euo pipefail
case "${1:-}" in
    --runtime)
        [[ $# == 1 ]] || exit 2
        [[ $EUID == 0 ]] || { echo 'Run as root on VOXL.' >&2; exit 1; }
        apt-get update
        apt-get install -y mosquitto mosquitto-clients
        echo 'The distribution may start mosquitto.service; switch services as described in README.md.'
        ;;
    --check|'')
        [[ $# -le 1 ]] || exit 2
        command -v python3 >/dev/null
        echo 'Packaging ready (Python 3); no compiler or cross-build is needed.'
        ;;
    *) echo 'Usage: ./install_build_deps.sh [--check | --runtime]' >&2; exit 2 ;;
esac
