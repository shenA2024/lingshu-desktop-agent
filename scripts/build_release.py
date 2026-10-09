"""Build an explicit source allowlist; local application data is never packaged."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from version import VERSION

FIXED = [
    'version.py', 'VERSIONING.md', 'agent.py', 'harness_runner.cjs', 'workbench.py',
    'metrics.py', 'mcp_bridge.py', 'data_backup.py', 'doctor.py', 'dependencies.py',
    'bootstrap.py', 'dependencies.lock.json', 'config.json', 'requirements.txt',
    'requirements-dev.txt', 'setup.ps1', 'start.ps1', 'stop.ps1', '启动灵枢.cmd',
    '首次安装.cmd', '检查环境.cmd', 'README.md', 'DSH_INTEGRATION.md', 'THIRD_PARTY.md',
    'VALIDATION.md', '桌面Agent体验说明.md', 'LICENSE', 'CONTRIBUTING.md',
    'scripts/build_release.py',
]
EVIDENCE = [
    'stability-031-home.png', 'stability-031-data-light.png',
    'stability-031-data-dark.png', 'stability-031-data-warm.png',
    'stability-031-real-validation.json', 'stability-031-ui-validation.json',
    'stability-031-contrast-validation.json', 'stability-031-unittest.txt',
    'agent-real-validation.json',
]
FORBIDDEN = {'data', '.venv', '.git', 'vendor', 'references', 'harness-home', '__pycache__'}
PREFIX = f'lingshu-desktop-agent-{VERSION}-preview/'
TARGET = ROOT / 'dist' / f'lingshu-desktop-agent-{VERSION}-windows-preview.zip'


def files():
    result = list(FIXED) + ['artifacts/' + name for name in EVIDENCE]
    for directory, extensions in [('static', {'.html', '.js', '.css', '.svg'}),
                                  ('tests', {'.py'}), ('licenses', {'.txt'}),
                                  ('docs/images', {'.png'})]:
        result += [p.relative_to(ROOT).as_posix() for p in (ROOT / directory).rglob('*')
                   if p.is_file() and p.suffix in extensions and not any(part in FORBIDDEN for part in p.parts)]
    result = sorted(set(result))
    for relative in result:
        path = ROOT / relative
        assert path.is_file() and not path.is_symlink(), relative
        assert path.resolve().is_relative_to(ROOT.resolve()), relative
        assert not any(part in FORBIDDEN for part in Path(relative).parts), relative
    return result


def build():
    included = files()
    manifest = {'version': VERSION, 'files': {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in included}}
    TARGET.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(TARGET, 'w', zipfile.ZIP_DEFLATED) as archive:
        for relative in included:
            archive.write(ROOT / relative, PREFIX + relative)
        archive.writestr(PREFIX + 'PACKAGE_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    digest = hashlib.sha256(TARGET.read_bytes()).hexdigest()
    TARGET.with_suffix('.zip.sha256').write_text(digest + '  ' + TARGET.name + '\n', encoding='utf-8')
    print(json.dumps({'package': TARGET.name, 'version': VERSION, 'files': len(included),
                      'bytes': TARGET.stat().st_size, 'sha256': digest}, ensure_ascii=False))


def verify():
    expected = set(files())
    with zipfile.ZipFile(TARGET) as archive:
        assert archive.testzip() is None
        manifest = json.loads(archive.read(PREFIX + 'PACKAGE_MANIFEST.json'))
        assert manifest['version'] == VERSION
        assert set(manifest['files']) == expected
        assert set(archive.namelist()) == {PREFIX + f for f in expected | {'PACKAGE_MANIFEST.json'}}
        for relative, digest in manifest['files'].items():
            assert hashlib.sha256(archive.read(PREFIX + relative)).hexdigest() == digest, relative
            assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest, relative
    checksum = TARGET.with_suffix('.zip.sha256').read_text('utf-8').split()[0]
    assert hashlib.sha256(TARGET.read_bytes()).hexdigest() == checksum
    print(json.dumps({'ok': True, 'version': VERSION, 'files': len(expected)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    verify() if args.verify else build()
