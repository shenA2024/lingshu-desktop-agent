"""Resolve immutable, external upstream checkouts; never fall back to vendor."""
from __future__ import annotations

import json
import os
from pathlib import Path
import hashlib

BASE = Path(__file__).resolve().parent
LOCK = json.loads((BASE / "dependencies.lock.json").read_text(encoding="utf-8"))


class DependencyError(RuntimeError):
    pass


def cache_root():
    override = os.environ.get("LINGSHU_LAB_DEPENDENCIES")
    default = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".cache")) / "LingshuWorldModelLab" / "dependencies"
    root = Path(override).expanduser().resolve() if override else default.resolve()
    if root == BASE or BASE in root.parents:
        raise DependencyError("依赖缓存必须放在实验台目录之外；设置 LINGSHU_LAB_DEPENDENCIES。")
    return root


def validate(name, root=None):
    spec = LOCK[name]
    path = (root or cache_root()) / f"{name}-{spec['commit']}"
    try:
        if not (path / ".source-manifest.json").exists():
            raise DependencyError("固定版本 checkout 缺失")
        manifest = json.loads((path / ".source-manifest.json").read_text(encoding="utf-8"))
        if manifest["commit"] != spec["commit"] or manifest["archive_sha256"] != spec["sha256"]:
            raise DependencyError("依赖提交 / 归档摘要与锁文件不一致")
        for filename, digest in manifest["files"].items():
            source = path / filename
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                raise DependencyError("上游文件缺失或已修改：" + filename)
        known = set(manifest["files"]) | {".source-manifest.json"}
        extra = [p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.relative_to(path).as_posix() not in known]
        if extra:
            raise DependencyError("依赖出现未登记文件；请使用新的外置缓存目录")
        for resource in spec["resources"]:
            if not (path / resource).is_file():
                raise DependencyError("缺少上游资源：" + resource)
    except (DependencyError, ValueError, KeyError, OSError) as exc:
        raise DependencyError(f"{name}: {exc}\n运行 .\\setup.ps1（或 python bootstrap.py --deps-only），缓存：{path}") from exc
    return path


def resolve():
    return validate("lingshu"), validate("dsh-memory")
