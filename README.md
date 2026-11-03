# VOXL MQTT Server

A small setup package that runs the distribution's Mosquitto broker as
`voxl-mqtt-server.service`. No custom broker application, compiler, Docker, or
Modal Pipe dependencies are required. The scripts and configuration are packaged
as `Architecture: all`; VOXL installs its own native Mosquitto binary.

## Build and deploy

On the development machine (Python 3 required):

```sh
./build.sh qrb5165          # also accepts qrb5165-2, arm64, or native
# Output: build/voxl-mqtt-server_0.1.0_all.deb
./deploy_to_voxl.sh --help
./deploy_to_voxl.sh adb --dry-run
./deploy_to_voxl.sh adb
# Alternatively: ./deploy_to_voxl.sh ssh 192.168.1.100
```

`./make_package.sh` builds the same package directly. Packaging uses Python's
standard library to write the standard Debian archive, so it also works on macOS.
The deploy script transfers the package and runs `dpkg -i`; it does not fetch
missing dependencies. Install the dependencies first on VOXL:

```sh
apt-get update
apt-get install mosquitto mosquitto-clients
```

Alternatively, copy this project's `install_build_deps.sh` onto VOXL and run it
as root with `--runtime`. Installing the distribution's Mosquitto package can
start its stock service. Before starting the VOXL service, switch explicitly:

```sh
systemctl disable --now mosquitto.service
systemctl enable voxl-mqtt-server
systemctl start voxl-mqtt-server
systemctl status voxl-mqtt-server
journalctl -u voxl-mqtt-server.service -f
```

The VOXL unit conflicts with `mosquitto.service` so systemd will not run both
units together. Other independently started brokers can still occupy the port;
stop them before starting this service. Installing this package does not start,
enable, or stop either service. On VOXL without repository access, supply the
Mosquitto package and its dependencies separately; this package is not an offline
bundle of the broker. VOXL image compatibility requires checking the available
Mosquitto package and testing on the target device.

## Configuration

The broker reads `/etc/modalai/voxl-mqtt-server.conf` using native Mosquitto
syntax. The default listener is **0.0.0.0:1883** (all IPv4 interfaces), with anonymous access,
persistence disabled, and logs sent to the system journal. Configure username/password
authentication before using the broker on an untrusted network. The existing MAVLink
MQTT client's default `localhost:1883` settings can connect to it.

```sh
voxl-configure-mqtt-server --config
voxl-configure-mqtt-server --edit
systemctl restart voxl-mqtt-server
```

Set `EDITOR` to an editor executable if desired; otherwise nano or vi is used.
To create a missing config, use `--save-default`. To reset an existing config,
use `--save-default --force`; the helper first makes a uniquely named backup
beside the original. Debian treats the main file as a conffile and preserves
local edits during upgrades, subject to normal dpkg conffile prompts. The default
template lives under `/usr/share/voxl-mqtt-server/`.

Other devices can connect using the VOXL IP address, for example `192.168.8.1`.
To restrict access, bind the listener to a specific interface address or to
`127.0.0.1` for local access only. Anonymous clients can publish and subscribe
from any network that can reach port 1883. The file includes commented password,
ACL, and TLS settings.
### Username and password authentication

On VOXL, create a password file and add a user. The command prompts for the
password without putting it in shell history:

```sh
mosquitto_passwd -c /etc/modalai/voxl-mqtt-server.passwd myuser
chown root:mosquitto /etc/modalai/voxl-mqtt-server.passwd
chmod 0640 /etc/modalai/voxl-mqtt-server.passwd
```

Edit `/etc/modalai/voxl-mqtt-server.conf` with
`voxl-configure-mqtt-server --edit`. Set anonymous access off and configure the
password file:

```conf
allow_anonymous false
password_file /etc/modalai/voxl-mqtt-server.passwd
```

Save the file and restart the broker:

```sh
systemctl restart voxl-mqtt-server
systemctl status voxl-mqtt-server
```

Add another account with `mosquitto_passwd /etc/modalai/voxl-mqtt-server.passwd anotheruser`
(without `-c`, which creates or overwrites the file). Restart the broker after
changing the password file. To remove a user, run
`mosquitto_passwd -D /etc/modalai/voxl-mqtt-server.passwd username`, then restart.

Use the account from a client like this:

```sh
mosquitto_sub -h 192.168.8.1 -p 1883 -t 'voxl/#' -u myuser -P 'your-password' -v
mosquitto_pub -h 192.168.8.1 -p 1883 -t test -m 'hello' -u myuser -P 'your-password'
```

For network connections requiring encryption, configure TLS as well. Certificates,
keys, ACLs and password files must be readable by the `mosquitto` service user.
Match the client host, port, credentials and TLS settings to the broker.

For retained messages and persistent sessions across restarts, change
`persistence false` to `persistence true` and uncomment `persistence_location`.
Systemd creates `/var/lib/voxl-mqtt-server` owned by the service user. This
introduces periodic flash writes. Settings must be supported by the Mosquitto
version installed on the target; the shipped defaults use longstanding options.

## Verify on VOXL

In one terminal:

```sh
mosquitto_sub -h 127.0.0.1 -t voxl/test -C 1 -W 10
```

In another:

```sh
mosquitto_pub -h 127.0.0.1 -t voxl/test -m hello
```

The subscriber should print `hello`. Then start the MAVLink MQTT client and
subscribe to `voxl/mavlink/+` to check actual telemetry. Restart the broker and
confirm that the client reconnects. For host-side broker and package smoke tests:

```sh
python3 tools/smoke_test.py
```

## Remove

```sh
apt-get remove voxl-mqtt-server
# To remove its packaged configuration as well:
apt-get purge voxl-mqtt-server
```

Removal stops and disables the VOXL service. User-created credentials,
certificates, backups and broker state are preserved. Mosquitto remains installed;
if you want to return to its stock service, enable it explicitly afterwards.

The unit is installed under `/etc/systemd/system` so VOXL’s
`voxl-inspect-services` discovers it and can identify its owning package.
Its CPU reading may be blank because the process is named `mosquitto`.

Validated on a VOXL running Ubuntu 18.04 with Mosquitto 1.4.15: package
installation, enabled/running status in `voxl-inspect-services -v`, loopback
publish/subscribe, and service restart. Runtime dependencies were transferred
via ADB because the device could not resolve the Ubuntu package server.

## Mosquitto client configuration warning in ADB shells

Some VOXL images start ADB without a `HOME` environment variable. Mosquitto's
command-line clients then print `Warning: Unable to locate configuration
directory, default config not loaded.` even when publishing succeeds.

This package installs `/etc/systemd/system/adbd.service.d/voxl-mqtt-home.conf`,
which sets `HOME=/home/root` for the root ADB sessions used by VOXL. The setting
persists across reboot and reinstall. If the root account uses a different home,
edit the drop-in to match the account's entry in `/etc/passwd`.

After first installing this fix, reboot VOXL or run
`systemctl restart adbd.service` and reconnect ADB. Restarting ADB disconnects
existing ADB shells. The package reloads systemd but does not restart ADB during
installation, so it cannot interrupt the package installation itself. Existing
shells can use `export HOME=/home/root` until they reconnect after the restart.
No client configuration file is required; command-line arguments still work.
