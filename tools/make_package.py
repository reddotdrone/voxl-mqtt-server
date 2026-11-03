"""Build a standard Debian ar archive using only Python's standard library."""
import io
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parent.parent


def archive(entries):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w:gz', format=tarfile.GNU_FORMAT) as tar:
        directories = set()
        for _, destination, _ in entries:
            directories.update(str(p) for p in Path(destination).parents if str(p) != '.')
        for directory in sorted(directories, key=lambda p: (p.count('/'), p)):
            info = tarfile.TarInfo('./' + directory)
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            info.uname = info.gname = 'root'
            tar.addfile(info)
        for source, destination, mode in entries:
            data = source.read_bytes()
            info = tarfile.TarInfo('./' + destination)
            info.size = len(data)
            info.mode = mode
            info.uid = info.gid = 0
            info.uname = info.gname = 'root'
            tar.addfile(info, io.BytesIO(data))
    return out.getvalue()


def member(name, data):
    header = f'{name + "/":<16}{0:<12}{0:<6}{0:<6}{"100644":<8}{len(data):<10}`\n'
    return header.encode('ascii') + data + (b'\n' if len(data) % 2 else b'')


def main():
    control = ROOT / 'pkg/control'
    version = next(line.split(': ', 1)[1] for line in
                   (control / 'control').read_text().splitlines() if line.startswith('Version: '))
    metadata = [(p, p.name, 0o755 if p.name in ('postinst', 'prerm', 'postrm') else 0o644)
                for p in sorted(control.iterdir()) if p.is_file()]
    payload = [
        (ROOT / 'config/voxl-mqtt-server.conf', 'etc/modalai/voxl-mqtt-server.conf', 0o644),
        (ROOT / 'config/voxl-mqtt-server.conf', 'usr/share/voxl-mqtt-server/voxl-mqtt-server.conf', 0o644),
        (ROOT / 'scripts/voxl-configure-mqtt-server', 'usr/bin/voxl-configure-mqtt-server', 0o755),
        (ROOT / 'services/voxl-mqtt-server.service', 'etc/systemd/system/voxl-mqtt-server.service', 0o644),
        (ROOT / 'services/adbd.service.d/voxl-mqtt-home.conf', 'etc/systemd/system/adbd.service.d/voxl-mqtt-home.conf', 0o644),
        (ROOT / 'README.md', 'usr/share/doc/voxl-mqtt-server/README.md', 0o644),
    ]
    output = ROOT / 'build' / f'voxl-mqtt-server_{version}_all.deb'
    output.parent.mkdir(exist_ok=True)
    output.write_bytes(b'!<arch>\n' + member('debian-binary', b'2.0\n') +
                       member('control.tar.gz', archive(metadata)) +
                       member('data.tar.gz', archive(payload)))
    print(f'Built {output}')


if __name__ == '__main__':
    main()
