"""Organization persistence, protected MCP settings and the installed MCP protocol."""
import asyncio
from contextlib import asynccontextmanager
from io import BytesIO
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from unittest.mock import AsyncMock
import zipfile

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import AgentService, MessageInput, routes
from data_backup import create_backup, restore_backup
from tool_connections import ConnectionInput

HARNESS = Path(os.environ.get('LINGSHU_DSH_EXE', r'D:\DeepSeek桌面版\DeepSeek Harness.exe'))
FIXTURE = '''
import json, os, sys, time
for line in sys.stdin:
    request=json.loads(line)
    if 'id' not in request:continue
    method=request['method']
    if method=='initialize':
        result={'protocolVersion':request['params']['protocolVersion'],'capabilities':{'tools':{}},'serverInfo':{'name':'explicit-test-fixture','version':'1'}}
    elif method=='tools/list':
        result={'tools':[{'name':'fixture_add','description':'Explicit fixture: add two numbers.','inputSchema':{'type':'object','properties':{'a':{'type':'number'},'b':{'type':'number'}},'required':['a','b']}}]}
    elif method=='tools/call':
        args=request['params']['arguments']
        result={'content':[{'type':'text','text':str(args['a']+args['b'])}]}
    else:result={}
    print(json.dumps({'jsonrpc':'2.0','id':request['id'],'result':result}),flush=True)
'''


class OrganizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        @asynccontextmanager
        async def lifespan(app):
            self.service = AgentService(self.root, 8794)
            yield
            await self.service.close()
        app = FastAPI(lifespan=lifespan)
        app.include_router(routes(lambda: self.service))
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None,None,None)
        self.temp.cleanup()

    def test_pin_archive_search_restore_and_restart(self):
        first = self.client.post('/api/agent/chats').json()
        second = self.client.post('/api/agent/chats').json()
        target = '/api/agent/chats/' + first['id']
        self.assertEqual(self.client.patch(target,json={'title':'Organization Sentinel','pinned':True}).status_code,200)
        self.assertEqual(self.client.get('/api/agent/chats').json()[0]['id'],first['id'])
        self.assertEqual(len(self.client.get('/api/agent/chats?view=pinned').json()),1)
        self.assertEqual(self.client.patch(target,json={'archived':True}).status_code,200)
        self.assertEqual([c['id'] for c in self.client.get('/api/agent/chats').json()],[second['id']])
        self.assertEqual(self.client.get('/api/agent/chats?view=archived&query=sentinel').json()[0]['id'],first['id'])
        response=self.client.post(target+'/messages',json={'content':'blocked','request_id':'request-sentinel'})
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.client.get(target).json()['turns'],[])
        self.client.__exit__(None,None,None)
        self.client.__enter__()
        self.assertTrue(self.service.get(first['id'])['archived'])
        self.assertEqual(self.client.patch(target,json={'archived':False}).status_code,200)
        self.assertEqual(self.client.get('/api/agent/chats').json()[0]['id'],first['id'])
        self.assertEqual(self.client.get('/api/agent/chats?view=invalid').status_code,422)
        self.assertEqual(self.client.patch(target,json={'title':'  '}).status_code,422)

    def test_old_records_default_and_backup_preserves_organization(self):
        chat=self.client.post('/api/agent/chats').json()
        chat.pop('pinned');chat.pop('archived')
        self.assertFalse(self.service.summary(chat)['archived'])
        chat.update(pinned=True,archived=True)
        archive=create_backup([chat],[],self.root/'memory')
        destination=self.root/'restored'
        restore_backup(BytesIO(archive),destination)
        restored=AgentService(destination,8794)
        self.assertTrue(restored.get(chat['id'])['pinned'])
        self.assertTrue(restored.get(chat['id'])['archived'])
        self.assertTrue(restored.get(chat['id'])['read_only'])
        asyncio.run(restored.close())

    def test_tool_schema_reservation_and_transport_validation(self):
        rejected=self.client.put('/api/agent/tools',json={'name':'invalid!','transport':'stdio','command':'python','env':{'TOKEN':'INVALID-REQUEST-SECRET'}})
        self.assertEqual(rejected.status_code,422)
        self.assertNotIn('INVALID-REQUEST-SECRET',rejected.text)
        for data in [dict(name='lingshu_lab',transport='stdio',command='python'),
                     dict(name='../bad',transport='stdio',command='python'),
                     dict(name='x',transport='streamable-http',url='https://user:password@example.com/mcp'),
                     dict(name='x',transport='streamable-http',url='http://localhost/mcp?token=secret'),
                     dict(name='x',transport='stdio',command='python',headers={'Authorization':'secret'}),
                     dict(name='x',transport='stdio',command='python',env={'BAD':'line\nbreak'})]:
            with self.assertRaises(ValidationError):ConnectionInput(**data)
        response=self.client.put('/api/agent/tools',json={'name':'fixture','transport':'stdio','command':sys.executable,'args':['-V']})
        self.assertEqual(response.status_code,200,response.text)
        self.assertFalse(response.json()['enabled'])
        self.assertEqual(self.client.patch('/api/agent/tools/fixture',json={'enabled':True}).status_code,409)

    @unittest.skipUnless(os.name=='nt','Windows DPAPI')
    def test_secrets_never_exposed_in_config_api_overlay_or_backup(self):
        data={'name':'fixture','transport':'stdio','command':sys.executable,'env':{'TOKEN':'CREDENTIAL-SENTINEL'}}
        response=self.client.put('/api/agent/tools',json=data)
        self.assertEqual(response.status_code,200,response.text)
        self.assertNotIn('CREDENTIAL-SENTINEL',response.text)
        self.assertNotIn('CREDENTIAL-SENTINEL',self.service.tools.path.read_text())
        self.assertNotIn(b'CREDENTIAL-SENTINEL',(self.service.root/'tool-fixture.dpapi').read_bytes())
        self.assertEqual(self.service.tools.spec('fixture')['env']['TOKEN'],'CREDENTIAL-SENTINEL')
        data['env']['TOKEN']=''
        self.client.put('/api/agent/tools',json=data)
        self.assertEqual(self.service.tools.spec('fixture')['env']['TOKEN'],'CREDENTIAL-SENTINEL')
        self.service.tools.entries['fixture'].update(check={'ok':True,'tools':[]},enabled=True)
        patch=self.service.prepare('en','fixture-turn').read_text()
        self.assertNotIn('CREDENTIAL-SENTINEL',patch)
        self.assertIn('lingshu-tool-fixture',patch)
        archive=create_backup([],[],self.root/'memory')
        with zipfile.ZipFile(BytesIO(archive)) as z:
            self.assertFalse(any('tool' in name or 'dpapi' in name for name in z.namelist()))
        self.assertEqual(self.client.delete('/api/agent/tools/fixture').status_code,200)
        self.assertFalse((self.service.root/'tool-fixture.dpapi').exists())

    def test_concurrent_turn_language_overlays_are_immutable(self):
        english=self.service.prepare('en','english').read_text()
        chinese=self.service.prepare('zh-CN','chinese').read_text()
        self.assertIn('Respond in English',english)
        self.assertNotIn('Respond in English',chinese)
        self.assertEqual((self.service.root/'turn-english.patch.yml').read_text(),english)


@unittest.skipUnless(HARNESS.is_file(),'Installed supported Harness integration')
class InstalledMCPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.fixture=self.root/'mcp_fixture.py'
        self.fixture.write_text(FIXTURE,'utf-8')
        self.service=AgentService(self.root,8794)
        self.service.settings['executable']=str(HARNESS)

    async def asyncTearDown(self):
        await self.service.close()
        self.temp.cleanup()

    async def test_actual_sdk_discovers_tools_and_relay_calls_without_model(self):
        self.service.tools.save(ConnectionInput(name='fixture',transport='stdio',command=sys.executable,args=['-X','utf8',str(self.fixture)]))
        checked=await self.service.tools.check('fixture')
        self.assertTrue(checked['ok'],checked)
        self.assertEqual(checked['tools'][0]['name'],'fixture_add')
        self.service.tools.entries['fixture']['enabled']=True;self.service.tools.write()
        from agent import BASE,ProcessTree
        env=os.environ|{'ELECTRON_RUN_AS_NODE':'1','LINGSHU_DSH_CLI':str(self.service.paths()[1]),'LINGSHU_MCP_SPEC':json.dumps(self.service.tools.spec('fixture'))}
        process=await asyncio.create_subprocess_exec(str(HARNESS),'--expose-internals',str(BASE/'external_mcp.cjs'),env=env,
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
        tree=ProcessTree(process.pid)
        try:
            async def request(id,method,params):
                process.stdin.write((json.dumps({'jsonrpc':'2.0','id':id,'method':method,'params':params})+'\n').encode());await process.stdin.drain()
                return json.loads(await asyncio.wait_for(process.stdout.readline(),8))
            await request(1,'initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'fixture','version':'1'}})
            listed=await request(2,'tools/list',{})
            self.assertEqual(listed['result']['tools'][0]['name'],'fixture_add')
            called=await request(3,'tools/call',{'name':'fixture_add','arguments':{'a':19,'b':23}})
            self.assertEqual(called['result']['content'][0]['text'],'42')
            process.stdin.close()
            await asyncio.wait_for(process.wait(),8)
        finally:
            tree.close()
            if process.returncode is None:process.kill();await process.wait()

    @unittest.skipUnless(os.name=='nt','Windows DPAPI')
    async def test_streamable_http_handshake_with_encrypted_header(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                if self.headers.get('Authorization')!='Bearer HTTP-FIXTURE-SENTINEL':
                    self.send_error(401);return
                request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if 'id' not in request:
                    self.send_response(202);self.end_headers();return
                if request['method']=='initialize':
                    result={'protocolVersion':request['params']['protocolVersion'],'capabilities':{'tools':{}},'serverInfo':{'name':'http-test-fixture','version':'1'}}
                else:
                    result={'tools':[{'name':'http_fixture','inputSchema':{'type':'object'}}]}
                payload=json.dumps({'jsonrpc':'2.0','id':request['id'],'result':result}).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
            def do_GET(self):self.send_error(405)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            self.service.tools.save(ConnectionInput(name='http_fixture',transport='streamable-http',
                url=f'http://127.0.0.1:{server.server_port}/mcp',headers={'Authorization':'Bearer HTTP-FIXTURE-SENTINEL'}))
            result=await self.service.tools.check('http_fixture')
            self.assertTrue(result['ok'],result)
            self.assertEqual(result['tools'][0]['name'],'http_fixture')
            self.assertNotIn('HTTP-FIXTURE-SENTINEL',self.service.tools.path.read_text())
        finally:
            await asyncio.to_thread(server.shutdown);server.server_close();thread.join()

    async def test_cancel_connection_check_kills_owned_child(self):
        fixture=self.root/'wait.py'
        fixture.write_text('import os, pathlib, time; pathlib.Path(__file__).with_suffix(".pid").write_text(str(os.getpid())); time.sleep(90)','utf-8')
        self.service.tools.save(ConnectionInput(name='wait_fixture',transport='stdio',command=sys.executable,args=[str(fixture)]))
        task=asyncio.create_task(self.service.tools.check('wait_fixture'))
        for _ in range(100):
            if fixture.with_suffix('.pid').exists():break
            await asyncio.sleep(.05)
        self.assertTrue(fixture.with_suffix('.pid').exists())
        pid=int(fixture.with_suffix('.pid').read_text())
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(self.service.tools.checking,set())
        if os.name=='nt':
            import ctypes
            from ctypes import wintypes
            k=ctypes.WinDLL('kernel32',use_last_error=True)
            k.OpenProcess.restype=wintypes.HANDLE
            k.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
            k.CloseHandle.argtypes=[wintypes.HANDLE]
            handle=k.OpenProcess(0x1000,False,pid)
            if handle:
                exit_code=wintypes.DWORD();k.GetExitCodeProcess(handle,ctypes.byref(exit_code));k.CloseHandle(handle)
                self.assertNotEqual(exit_code.value,259)


if __name__=='__main__':unittest.main()
