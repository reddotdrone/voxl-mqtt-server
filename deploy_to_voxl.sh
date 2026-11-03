#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: ./deploy_to_voxl.sh [adb | ssh [IP-address]] [--dry-run]

Default transport is ADB. SSH uses the address argument or VOXL_IP.
VOXL_SSH_USER defaults to root and VOXL_SSH_PORT defaults to 22.
Run ./build.sh && ./make_package.sh first.
The package installs the service but does not start or enable it.
USAGE
}

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
version="$(awk '/^Version: / { print $2 }' "$repo_dir/pkg/control/control")"
package_name="voxl-mqtt-server_${version}_all.deb"
package="$repo_dir/build/$package_name"

mode="${1:-adb}"
if [[ "$mode" == "--help" || "$mode" == "-h" ]]; then usage; exit 0; fi
if [[ "$mode" != "adb" && "$mode" != "ssh" ]]; then usage >&2; exit 2; fi
shift $(( $# > 0 ? 1 : 0 ))

address=""
if [[ "$mode" == "ssh" && $# -gt 0 && "$1" != "--dry-run" ]]; then
  address="$1"
  shift
fi
dry_run=false
if [[ $# -gt 0 && "$1" == "--dry-run" ]]; then dry_run=true; shift; fi
if [[ $# -ne 0 ]]; then usage >&2; exit 2; fi

if [[ ! -f "$package" ]]; then
  echo "Missing $package; run ./build.sh and ./make_package.sh first" >&2
  exit 1
fi

if [[ "$mode" == "ssh" ]]; then
  address="${address:-${VOXL_IP:-}}"
  if [[ -z "$address" ]]; then
    echo "Specify an SSH address or set VOXL_IP" >&2
    exit 2
  fi
  if [[ "$address" =~ ^[0-9]{1,3}$ ]]; then address="192.168.1.$address"; fi
  ssh_user="${VOXL_SSH_USER:-root}"
  ssh_port="${VOXL_SSH_PORT:-22}"
  if [[ ! "$ssh_port" =~ ^[0-9]+$ ]]; then
    echo "VOXL_SSH_PORT must be numeric" >&2
    exit 2
  fi
  remote="$ssh_user@$address"
  echo "Deploying $package_name to $remote over SSH"
  if $dry_run; then
    echo "ssh -p $ssh_port $remote command -v dpkg"
    echo "scp -O -P $ssh_port $package $remote:/data/$package_name"
    echo "ssh -p $ssh_port $remote dpkg -i /data/$package_name"
    exit 0
  fi
  command -v ssh >/dev/null || { echo "ssh is required" >&2; exit 1; }
  command -v scp >/dev/null || { echo "scp is required" >&2; exit 1; }
  ssh -p "$ssh_port" "$remote" 'command -v dpkg >/dev/null'
  # VOXL SSH images may provide SCP without an SFTP subsystem.
  scp -O -P "$ssh_port" "$package" "$remote:/data/$package_name"
  ssh -p "$ssh_port" "$remote" "dpkg -i /data/$package_name"
else
  echo "Deploying $package_name over ADB"
  if $dry_run; then
    echo "adb shell command -v dpkg"
    echo "adb push $package /data/$package_name"
    echo "adb shell dpkg -i /data/$package_name"
    exit 0
  fi
  command -v adb >/dev/null || { echo "adb is required" >&2; exit 1; }
  adb get-state >/dev/null
  adb shell 'command -v dpkg >/dev/null'
  adb push "$package" "/data/$package_name"
  adb shell "dpkg -i /data/$package_name"
fi

echo "Installed voxl-mqtt-server. Install Mosquitto dependencies if needed; see README.md to switch services and start the broker."
