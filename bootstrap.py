"""Fetch pinned official sources outside this lab and install Python dependencies."""
import argparse
import subprocess
import sys
import hashlib
import io
import json
from pathlib import Path
import tempfile
from urllib.request import urlopen
import zipfile
from dependencies import BASE, LOCK, DependencyError, cache_root, resolve, validate


def install_sources():
    root = cache_root()
    root.mkdir(parents=True, exist_ok=True)
    for name, spec in LOCK.items():
        target = root / f"{name}-{spec['commit']}"
        if target.exists():
            validate(name, root)  # Do not reset or repair an existing checkout.
            continue
        archive = root.parent / "archives" / f"{name}-{spec['commit']}.zip"
        archive.parent.mkdir(parents=True, exist_ok=True)
        if archive.is_file() and hashlib.sha256(archive.read_bytes()).hexdigest() == spec["sha256"]:
            data = archive.read_bytes()
        else:
            with urlopen(spec["url"], timeout=90) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != spec["sha256"]:
                raise DependencyError("官方归档 SHA-256 不符：" + name)
            archive.write_bytes(data)
        with tempfile.TemporaryDirectory(prefix="install-", dir=root) as temp:
            staged = Path(temp) / "source"
            staged.mkdir()
            files = {}
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for member in z.infolist():
                    relative = Path(*Path(member.filename).parts[1:])
                    if member.is_dir():
                        continue
                    output = (staged / relative).resolve()
                    if staged.resolve() not in output.parents or member.external_attr >> 16 & 0o170000 == 0o120000:
                        raise DependencyError("不安全的归档条目：" + member.filename)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    payload = z.read(member)
                    output.write_bytes(payload)
                    files[relative.as_posix()] = hashlib.sha256(payload).hexdigest()
            (staged / ".source-manifest.json").write_text(json.dumps({"commit": spec["commit"], "archive_sha256": spec["sha256"], "files": files}, indent=2), encoding="utf-8")
            staged.rename(target)
        validate(name, root)
        print(f"{name}: {spec['commit']}")
    resolve()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--deps-only", action="store_true")
    parser.add_argument("--dev", action="store_true")
    args = parser.parse_args()
    try:
        install_sources()
        if not args.deps_only:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(BASE / ("requirements-dev.txt" if args.dev else "requirements.txt"))], check=True)
        print("依赖已核对。运行 .\\start.ps1 或 python -X utf8 workbench.py。")
    except (DependencyError, subprocess.CalledProcessError, OSError, ValueError) as exc:
        print("安装失败：" + str(exc) + "\n若下载中断，请保留现场并用新的 LINGSHU_LAB_DEPENDENCIES 目录重试。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
