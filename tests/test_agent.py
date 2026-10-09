"""Protocol/lifecycle tests use an explicit fixture; real-model evidence is separate."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from agent import AgentService, MessageInput, protect


FIXTURE = r'''
import json, os, subprocess, sys, time
text = sys.stdin.buffer.read().decode('utf-8')
def send(event): print(json.dumps(event,ensure_ascii=False),flush=True)
session = sys.argv[sys.argv.index('--session-id')+1] if '--session-id' in sys.argv else 'session-fixture-1'
send({'type':'session','sessionId':session})
send({'type':'status','phase':'turn_start'})
send({'type':'thinking','text':'PRIVATE_REASONING_SENTINEL'})
print('PRIVATE_STDERR_SENTINEL',file=sys.stderr,flush=True)
if text.startswith('WAIT'):
    child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(90)'])
    open('child.pid','w').write(str(child.pid))
    send({'type':'tool_call','callId':'call1','tool':'mcp__lingshu_lab__lingshu_run_scene','input':{'scenario':'perturbation'}})
    send({'type':'tool_result','callId':'call1','status':'completed','result':'{"id":"abcdef123456"}'})
    time.sleep(90)
else:
    send({'type':'text','text':'intermediate'})
    send({'type':'final','text':text+'|'+session})
    sys.exit(1 if text=='FAIL_WITH_FINAL' else 0)
'''


class AgentLifecycle(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lingshu-agent-test-')
        self.root = Path(self.temp.name)
        self.cancelled = []
        self.service = AgentService(self.root, 8797, self.cancelled.extend)
        self.fixture = self.root / 'fixture.py'
        self.fixture.write_text(FIXTURE, 'utf-8')
        self.service.command = lambda args: [sys.executable, '-X', 'utf8', str(self.fixture), *args]
        self.service.status = AsyncMock(return_value={'ready': True})
        self.chat = {'id':'chat1', 'title':'新对话', 'created_at':'2026-10-09', 'updated_at':'2026-10-09', 'harness_id':None,'turns':[]}
        self.service.chats['chat1'] = self.chat
        self.service.save(self.chat)

    async def asyncTearDown(self):
        await self.service.close()
        self.temp.cleanup()

    def message(self, content, key='request-0001'):
        return MessageInput(content=content, request_id=key)

    async def wait_finished(self):
        await asyncio.wait_for(self.service.jobs['chat1']['task'], 8)
        return self.chat['turns'][-1]

    async def test_literal_stdin_and_resume_with_real_identity(self):
        content = '中文 " & $(echo should-not-run) `literal`\n第二行'
        await self.service.submit('chat1', self.message(content))
        first = await self.wait_finished()
        self.assertEqual(first['status'], 'completed')
        self.assertEqual(first['answer'], content+'|session-fixture-1')
        await self.service.submit('chat1', self.message('继续', 'request-0002'))
        second = await self.wait_finished()
        self.assertEqual(second['answer'], '继续|session-fixture-1')
        self.assertEqual(self.chat['harness_id'], 'session-fixture-1')
        payload = json.dumps(self.chat)
        self.assertNotIn('PRIVATE_REASONING_SENTINEL', payload)
        self.assertNotIn('PRIVATE_STDERR_SENTINEL', payload)

    async def test_idempotent_retry_and_same_chat_exclusion(self):
        original = await self.service.submit('chat1', self.message('WAIT'))
        retry = await self.service.submit('chat1', self.message('WAIT'))
        self.assertEqual(original['id'], retry['id'])
        self.assertEqual(len(self.chat['turns']), 1)
        for request in [self.message('different'), self.message('new', 'request-0002')]:
            with self.assertRaises(HTTPException) as exc:
                await self.service.submit('chat1', request)
            self.assertEqual(exc.exception.status_code, 409)

    async def test_stop_kills_process_tree_and_cancels_owned_experiments(self):
        await self.service.submit('chat1', self.message('WAIT'))
        marker = self.service.workspace / 'child.pid'
        for _ in range(100):
            if marker.exists() and self.chat['turns'][-1]['run_ids']:
                break
            await asyncio.sleep(.03)
        self.assertTrue(marker.exists())
        child = int(marker.read_text())
        self.service.jobs['chat1']['stop'].set()
        turn = await self.wait_finished()
        self.assertEqual(turn['status'], 'cancelled')
        self.assertEqual(self.cancelled, ['abcdef123456'])
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.OpenProcess(0x1000, False, child)
            if handle:
                code = wintypes.DWORD()
                kernel.GetExitCodeProcess(handle, ctypes.byref(code))
                kernel.CloseHandle(handle)
                self.assertNotEqual(code.value, 259, 'Child process still active')

    async def test_nonzero_exit_with_final_is_failure(self):
        await self.service.submit('chat1', self.message('FAIL_WITH_FINAL'))
        turn = await self.wait_finished()
        self.assertEqual(turn['status'], 'failed')
        self.assertTrue(turn['answer'])
        self.assertTrue(turn['error'])

    async def test_restart_marks_inflight_interrupted_and_retains_history(self):
        self.chat['turns'] = [{'id':'t1','status':'running','user':'保留这句话','events':[]}]
        self.service.save(self.chat)
        await self.service.close()
        self.service = AgentService(self.root, 8797)
        turn = self.service.chats['chat1']['turns'][0]
        self.assertEqual(turn['status'], 'interrupted')
        self.assertEqual(turn['user'], '保留这句话')

    async def test_not_ready_does_not_append_or_launch(self):
        self.service.status = AsyncMock(return_value={'ready':False})
        with self.assertRaises(HTTPException) as exc:
            await self.service.submit('chat1', self.message('hello'))
        self.assertEqual(exc.exception.status_code, 503)
        self.assertEqual(self.chat['turns'], [])
        self.assertEqual(self.service.jobs, {})

    async def test_validation_tracks_configuration_and_survives_restart(self):
        self.service.status = AgentService.status.__get__(self.service)
        self.service.probe = AsyncMock(return_value={'installed':True, 'compatible':True,
            'credential_ready':True, 'version':'0.2.0-rc.2'})
        status = await self.service.status()
        self.assertFalse(status['verified'])
        await self.service.submit('chat1', self.message('hello'))
        await self.wait_finished()
        successful = await self.service.status()
        self.assertTrue(successful['verified'])
        self.assertTrue(successful['last_success_at'])
        self.service.settings['model'] = 'deepseek-v4-pro'
        self.assertFalse((await self.service.status())['verified'])
        self.service.settings['model'] = 'deepseek-flash'
        self.assertTrue((await self.service.status())['verified'])
        # Credential replacement also invalidates the former validation.
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY':'fixture-not-a-real-key'}):
            self.assertFalse((await self.service.status())['verified'])
        await self.service.close()
        self.service = AgentService(self.root, 8797)
        self.service.probe = AsyncMock(return_value={'installed':True, 'compatible':True,
            'credential_ready':True, 'version':'0.2.0-rc.2'})
        self.assertTrue((await self.service.status())['verified'])

    async def test_probe_diagnoses_missing_install_and_unsupported_version(self):
        self.service.settings['executable'] = str(self.root / 'missing.exe')
        status = await AgentService.status(self.service, force=True)
        self.assertFalse(status['ready'])
        self.assertEqual(status['diagnostic_code'], 'RUNTIME_NOT_FOUND')
        self.service.paths = lambda: (Path(sys.executable), self.fixture)
        self.service.command = lambda args: [sys.executable, '-c',
            'import json; print(json.dumps({"installed":True,"credential_ready":True,"version":"9.9.9"}))']
        status = await AgentService.status(self.service, force=True)
        self.assertTrue(status['installed'])
        self.assertFalse(status['ready'])
        self.assertEqual(status['diagnostic_code'], 'UNSUPPORTED_VERSION')

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI')
    async def test_dpapi_roundtrip_contains_no_plaintext(self):
        source = b'test-not-a-real-secret-20261009'
        encrypted = protect(source)
        self.assertNotIn(source, encrypted)
        self.assertEqual(protect(encrypted, decrypt=True), source)


if __name__ == '__main__':
    unittest.main()
