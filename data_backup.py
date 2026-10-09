"""Portable visible-data snapshots. Credentials and raw Harness logs are excluded."""
from __future__ import annotations

import argparse
import copy
from contextlib import closing
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import re
import sqlite3
import tempfile
import zipfile

LIMIT = 128 * 1024 * 1024
SCHEMA = 'lingshu-visible-data-v1'


def allowed(name):
    path = PurePosixPath(name)
    return (name == 'snapshot.json' or
            (name.startswith('memory/') and name.endswith('.md'))) and not (
                path.is_absolute() or '\\' in name or ':' in name or '..' in path.parts or name != path.as_posix())


def create_backup(chats, runs, memory_root):
    snapshot = {'schema': SCHEMA, 'created_at': datetime.now(timezone.utc).isoformat(),
                'chats': copy.deepcopy(list(chats)), 'runs': copy.deepcopy(list(runs))}
    for chat in snapshot['chats']:
        chat['harness_id'] = None
        chat['read_only'] = True
    payloads = {'snapshot.json': json.dumps(snapshot, ensure_ascii=False, indent=2).encode('utf-8')}
    total = len(payloads['snapshot.json'])
    root = Path(memory_root).resolve()
    for note in sorted(root.rglob('*.md')):
        if note.is_symlink() or not note.resolve().is_relative_to(root):
            continue
        total += note.stat().st_size
        if total > LIMIT or len(payloads) >= 10000:
            raise ValueError('数据超过当前备份上限（128 MB／10000 个文件），请先按对话或实验导出。')
        payloads['memory/' + note.relative_to(root).as_posix()] = note.read_bytes()
    if total > LIMIT:
        raise ValueError('数据超过当前备份上限（128 MB），请先按对话或实验导出。')
    manifest = {'schema': SCHEMA, 'files': [
        {'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        for name, data in payloads.items()]}
    output = BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in payloads.items():
            archive.writestr(name, data)
        archive.writestr('MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    return output.getvalue()


def restore_backup(archive_path, destination):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('恢复目录必须尚不存在；原数据不会被覆盖。')
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or len(names) > 10001 or sum(i.file_size for i in archive.infolist()) > LIMIT + 4*1024*1024:
            raise ValueError('备份包含重复文件或超过容量上限。')
        manifest = json.loads(archive.read('MANIFEST.json'))
        if manifest.get('schema') != SCHEMA or not isinstance(manifest.get('files'), list):
            raise ValueError('不支持的备份格式。')
        entries = manifest['files']
        if set(names) != {e['path'] for e in entries} | {'MANIFEST.json'} or len(entries) != len(names)-1:
            raise ValueError('备份文件清单不一致。')
        payloads = {}
        for entry in entries:
            name = entry['path']
            if not allowed(name):
                raise ValueError('备份包含未允许的文件路径。')
            data = archive.read(name)
            if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
                raise ValueError('备份摘要不匹配，文件可能已损坏。')
            payloads[name] = data
    snapshot = json.loads(payloads['snapshot.json'])
    if snapshot.get('schema') != SCHEMA:
        raise ValueError('备份数据版本不一致。')
    for kind, fields in [('chats', ('id','title','created_at','updated_at','turns')),
                         ('runs', ('id','title','scenario','status','frames','events','completed_ticks'))]:
        records = snapshot.get(kind)
        if not isinstance(records, list):
            raise ValueError('备份缺少有效的数据列表。')
        seen = set()
        for record in records:
            if not isinstance(record, dict) or any(field not in record for field in fields):
                raise ValueError('备份记录字段不完整。')
            identifier = record['id']
            if not isinstance(identifier, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,120}', identifier) or identifier in seen:
                raise ValueError('备份记录标识无效或重复。')
            seen.add(identifier)
    for chat in snapshot['chats']:
        chat.update(harness_id=None, read_only=True)
        for turn in chat['turns']:
            if not isinstance(turn, dict) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,120}', str(turn.get('id',''))):
                raise ValueError('备份对话轮次无效。')
            if turn.get('status') in ('running', 'cancelling'):
                turn.update(status='interrupted', error='备份中的未完成轮次。')
    for run in snapshot['runs']:
        if run['status'] in ('running','cancelling','saving'):
            run['status'] = 'interrupted'
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.lingshu-restore-', dir=destination.parent) as temporary:
        staged = Path(temporary) / 'data'
        (staged / 'agent').mkdir(parents=True)
        for relative, table, records in [('agent/chats.sqlite','chats',snapshot['chats']),
                                         ('sessions.sqlite','runs',snapshot['runs'])]:
            with closing(sqlite3.connect(staged / relative)) as db:
                db.execute(f'CREATE TABLE {table} (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
                db.executemany(f'INSERT INTO {table} VALUES (?,?)',
                    [(record['id'], json.dumps(record, ensure_ascii=False)) for record in records])
                db.commit()
        for name, data in payloads.items():
            if name.startswith('memory/'):
                target = staged.joinpath(*PurePosixPath(name).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        if destination.exists():
            raise ValueError('恢复目录已被创建，请选择另一目录。')
        staged.rename(destination)
    return {'chats': len(snapshot['chats']), 'runs': len(snapshot['runs']),
            'notes': len(payloads)-1, 'destination': str(destination)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='将灵枢可见数据备份恢复到全新目录；已有数据不会被覆盖。')
    parser.add_argument('archive', type=Path)
    parser.add_argument('--destination', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(restore_backup(args.archive, args.destination), ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        parser.exit(1, f'恢复失败：{exc}\n')
