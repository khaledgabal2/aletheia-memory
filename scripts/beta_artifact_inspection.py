"""Verify built README metadata and clean installed import identity."""
import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, required=True)
    parser.add_argument('--python', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    readme = (root / 'README.md').read_text().strip()
    wheel, = args.dist.glob('*.whl')
    source, = args.dist.glob('*.tar.gz')
    with zipfile.ZipFile(wheel) as archive:
        metadata, = [name for name in archive.namelist() if name.endswith('.dist-info/METADATA')]
        message = BytesParser().parsebytes(archive.read(metadata))
        assert message.get_payload(decode=True).decode('utf-8').strip() == readme, 'Wheel README differs from source'
    with tarfile.open(source) as archive:
        name, = [member for member in archive.getnames() if member.count('/') == 1 and member.endswith('/README.md')]
        assert archive.extractfile(name).read().decode().strip() == readme, 'Source README differs'
    code = ('import aletheia, json; from importlib.metadata import version; '
            'from aletheia.version import software_version; '
            'print(json.dumps(dict(path=aletheia.__file__, metadata=version("aletheia-memory"), '
            'runtime=software_version())))')
    installed = json.loads(subprocess.check_output([args.python, '-I', '-c', code], cwd=args.dist, text=True))
    assert installed['metadata'] == message['Version'] == installed['runtime']
    assert 'site-packages' in installed['path'], installed
    report = {'status': 'passed', 'installed': installed, 'readme_matches': ['wheel', 'sdist'],
              'artifacts': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [wheel, source]}}
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
