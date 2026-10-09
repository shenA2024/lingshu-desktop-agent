"""Backup integrity and non-overwriting restore behavior."""
from io import BytesIO
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zipfile

from data_backup import create_backup, restore_backup, SCHEMA


class PortableBackup(unittest.TestCase):
    def test_visible_data_roundtrip_excludes_credentials_and_preserves_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'memory/contextual').mkdir(parents=True)
            (root/'memory/contextual/note.md').write_text('backup note', 'utf-8')
            (root/'memory/_tokens.json').write_text('SECRET_SENTINEL', 'utf-8')
            chats = [{'id':'chat1','title':'title','created_at':'2026-10-09','updated_at':'2026-10-09',
                      'harness_id':'private-session','turns':[]}]
            payload = create_backup(chats, [], root/'memory')
            self.assertNotIn(b'SECRET_SENTINEL', payload)
            with zipfile.ZipFile(BytesIO(payload)) as archive:
                self.assertEqual(set(archive.namelist()), {'snapshot.json','memory/contextual/note.md','MANIFEST.json'})
                self.assertNotIn('private-session', archive.read('snapshot.json').decode())
            target = root/'restored'
            result = restore_backup(BytesIO(payload), target)
            self.assertEqual((result['chats'],result['notes']), (1,1))
            with closing(sqlite3.connect(target/'agent/chats.sqlite')) as db:
                recovered = json.loads(db.execute('SELECT data FROM chats').fetchone()[0])
            self.assertTrue(recovered['read_only'])
            self.assertIsNone(recovered['harness_id'])
            self.assertEqual((target/'memory/contextual/note.md').read_text(), 'backup note')
            before = (target/'memory/contextual/note.md').read_bytes()
            with self.assertRaises(ValueError):
                restore_backup(BytesIO(payload), target)
            self.assertEqual((target/'memory/contextual/note.md').read_bytes(), before)

    def test_corruption_and_path_traversal_are_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, digest in [('snapshot.json','incorrect'), ('memory/../../escape.md', hashlib.sha256(b'{}').hexdigest())]:
                output = BytesIO()
                with zipfile.ZipFile(output,'w') as archive:
                    archive.writestr(name,b'{}')
                    archive.writestr('MANIFEST.json',json.dumps({'schema':SCHEMA,'files':[
                        {'path':name,'bytes':2,'sha256':digest}]}))
                with self.assertRaises(ValueError):
                    restore_backup(BytesIO(output.getvalue()),root/'restored')
                self.assertFalse((root/'restored').exists())
                self.assertFalse((root/'escape.md').exists())
