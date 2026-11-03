"""Check package contents and exchange a message using the shipped broker config."""
import io
from pathlib import Path
import shutil
import socket
import subprocess
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
subprocess.run([str(ROOT / 'build.sh')], check=True)
package = max((ROOT / 'build').glob('voxl-mqtt-server_*_all.deb'), key=lambda p: p.stat().st_mtime)
raw = package.read_bytes()
assert raw[:8] == b'!<arch>\n'
members = {}
offset = 8
while offset < len(raw):
    header = raw[offset:offset + 60]
    assert header[58:] == b'`\n'
    size = int(header[48:58])
    members[header[:16].decode().strip().rstrip('/')] = raw[offset + 60:offset + 60 + size]
    offset += 60 + size + size % 2
assert members['debian-binary'] == b'2.0\n'
with tarfile.open(fileobj=io.BytesIO(members['control.tar.gz'])) as tar:
    assert b'Architecture: all' in tar.extractfile('./control').read()
    assert b'/etc/modalai/voxl-mqtt-server.conf' in tar.extractfile('./conffiles').read()
with tarfile.open(fileobj=io.BytesIO(members['data.tar.gz'])) as tar:
    config = tar.extractfile('./etc/modalai/voxl-mqtt-server.conf').read()
    assert config == (ROOT / 'config/voxl-mqtt-server.conf').read_bytes()
    assert tar.getmember('./usr/bin/voxl-configure-mqtt-server').mode == 0o755
    assert tar.getmember('./etc/systemd/system/voxl-mqtt-server.service').mode == 0o644
    assert all(m.uid == 0 and m.gid == 0 for m in tar.getmembers())
print('PASS: Debian archive, config, ownership, and executable permissions')
for script in list(ROOT.glob('*.sh')) + list((ROOT / 'scripts').iterdir()):
    subprocess.run(['bash', '-n', str(script)], check=True)
for name in ('postinst', 'prerm', 'postrm'):
    subprocess.run(['sh', '-n', str(ROOT / 'pkg/control' / name)], check=True)
print('PASS: shell syntax')
for name in ('mosquitto', 'mosquitto_pub', 'mosquitto_sub'):
    if not shutil.which(name):
        raise SystemExit(f'Missing {name}; install Mosquitto and its clients for broker tests')
with tempfile.TemporaryDirectory(prefix='voxl-mqtt-test-') as tmp:
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    path = Path(tmp) / 'broker.conf'
    path.write_bytes(config.replace(b'listener 1883 ', f'listener {port} '.encode()))
    with (Path(tmp) / 'broker.log').open('w+') as log:
        broker = subprocess.Popen(['mosquitto', '-c', str(path)], stdout=log, stderr=log)
        subscriber = None
        try:
            for _ in range(100):
                if broker.poll() is not None:
                    log.seek(0)
                    raise RuntimeError(log.read())
                try:
                    with socket.create_connection(('127.0.0.1', port), timeout=.1):
                        break
                except OSError:
                    time.sleep(.05)
            else:
                raise RuntimeError('Broker did not start')
            subscriber = subprocess.Popen(['mosquitto_sub', '-h', '127.0.0.1', '-p', str(port),
                                           '-t', 'voxl/test', '-C', '1', '-W', '5'],
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            # Repeated publication avoids depending on a fixed subscriber startup delay.
            for _ in range(40):
                subprocess.run(['mosquitto_pub', '-h', '127.0.0.1', '-p', str(port),
                                '-t', 'voxl/test', '-m', 'hello'], check=True)
                if subscriber.poll() is not None:
                    break
                time.sleep(.05)
            stdout, stderr = subscriber.communicate(timeout=6)
            assert subscriber.returncode == 0, stderr
            assert stdout.strip() == 'hello', stdout
            print('PASS: shipped config starts; local publish/subscribe delivers hello')
        finally:
            if subscriber and subscriber.poll() is None:
                subscriber.terminate()
                subscriber.wait(timeout=5)
            broker.terminate()
            broker.wait(timeout=5)
