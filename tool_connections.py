"""Explicit MCP connections; credentials are user-scoped DPAPI, outside backups."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field, SecretStr, model_validator


class ConnectionInput(BaseModel):
    name: str = Field(pattern=r'^[A-Za-z0-9_-]{1,32}$')
    transport: str = Field(pattern=r'^(stdio|streamable-http)$')
    command: str = Field(default='', max_length=1000)
    args: list[str] = Field(default_factory=list, max_length=100)
    cwd: str = Field(default='', max_length=1000)
    url: str = Field(default='', max_length=2000)
    env: dict[str, SecretStr] = Field(default_factory=dict, max_length=50)
    headers: dict[str, SecretStr] = Field(default_factory=dict, max_length=50)

    @model_validator(mode='after')
    def validate_transport(self):
        if self.name == 'lingshu_lab':
            raise ValueError('lingshu_lab is reserved')
        if self.transport == 'stdio':
            if not self.command.strip() or any(c in self.command for c in '\r\n\x00'):
                raise ValueError('A command is required')
            if any(len(arg) > 4000 or '\x00' in arg for arg in self.args):
                raise ValueError('Invalid argument')
            if self.url or self.headers:
                raise ValueError('stdio uses command, args and env')
        else:
            url = urlsplit(self.url)
            if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
                raise ValueError('Use an HTTP(S) endpoint; put credentials in headers')
            if self.command or self.args or self.cwd or self.env:
                raise ValueError('HTTP uses url and headers')
        for mapping in (self.env, self.headers):
            for key, value in mapping.items():
                if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]{0,100}', key) or len(value.get_secret_value()) > 8000 or any(c in value.get_secret_value() for c in '\r\n\x00'):
                    raise ValueError('Invalid environment variable or header')
        return self


class EnabledInput(BaseModel):
    enabled: bool


class PrivateValidationRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def private_handler(request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                # FastAPI normally echoes invalid input, including credentials.
                errors = [{key: error[key] for key in ('loc', 'msg', 'type')} for error in exc.errors()]
                return JSONResponse({'detail': errors}, status_code=422)
        return private_handler


class ToolConnections:
    def __init__(self, service):
        self.service = service
        self.path = service.root / 'tools.json'
        self.entries = json.loads(self.path.read_text('utf-8')) if self.path.exists() else {}
        self.checking = set()
        self.tasks = set()

    def write(self):
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.entries, ensure_ascii=False, indent=2), 'utf-8')
        temporary.replace(self.path)

    def get(self, name):
        if name not in self.entries:
            raise HTTPException(404, '工具连接不存在。')
        return self.entries[name]

    def public(self, name):
        return copy.deepcopy(self.get(name))

    def credentials(self, name):
        from agent import protect
        path = self.service.root / f'tool-{name}.dpapi'
        return json.loads(protect(path.read_bytes(), decrypt=True)) if path.exists() else {'env': {}, 'headers': {}}

    def spec(self, name):
        entry = self.get(name)
        return {k: entry[k] for k in ('transport', 'command', 'args', 'cwd', 'url')} | self.credentials(name)

    def revision(self):
        active = {name: {k: v for k, v in entry.items() if k != 'check'}
                  for name, entry in self.entries.items() if entry['enabled']}
        return hashlib.sha256(json.dumps(active, sort_keys=True).encode()).hexdigest()

    def ensure_idle(self):
        if self.service.jobs or self.checking:
            raise HTTPException(409, '请先停止正在运行的会话或等待连接检查完成。')

    def save(self, request):
        from agent import protect
        self.ensure_idle()
        name = request.name
        if name not in self.entries and len(self.entries) >= 20:
            raise HTTPException(409, '最多保存 20 个工具连接。')
        previous = self.credentials(name) if name in self.entries else {'env': {}, 'headers': {}}
        secret = {kind: {key: value.get_secret_value() or previous[kind].get(key, '')
                         for key, value in getattr(request, kind).items()} for kind in ('env', 'headers')}
        encoded = protect(json.dumps(secret).encode()) if any(secret.values()) else None
        path = self.service.root / f'tool-{name}.dpapi'
        if encoded:
            temporary = path.with_suffix('.tmp')
            temporary.write_bytes(encoded)
            temporary.replace(path)
        else:
            path.unlink(missing_ok=True)
        self.entries[name] = request.model_dump(exclude={'env', 'headers'}) | {
            'env': {key: '' for key in secret['env']}, 'headers': {key: '' for key in secret['headers']},
            'enabled': False, 'check': None, 'revision': uuid.uuid4().hex}
        self.write()
        return self.public(name)

    def overlays(self):
        from agent import BASE
        return [{'id': f'lingshu-tool-{name}', 'name': '@deepseek-ai/dsh-mcp-client', 'config': {
            'serverName': name, 'transport': 'stdio', 'command': sys.executable,
            'args': ['-X', 'utf8', str(BASE / 'tool_launch.py'), str(self.path), name,
                     str(self.service.paths()[0])], 'failOnStartupError': True}}
            for name, entry in self.entries.items() if entry['enabled']]

    async def check(self, name):
        from agent import BASE, ProcessTree, now
        if name in self.checking:
            raise HTTPException(409, '该连接正在检查。')
        entry = self.get(name)
        self.checking.add(name)
        task = asyncio.current_task()
        self.tasks.add(task)
        proc = tree = None
        result = {'ok': False, 'tools': [], 'checked_at': now(), 'code': 'MCP_CONNECTION_FAILED'}
        try:
            if not (await self.service.status())['compatible']:
                raise HTTPException(409, '请先配置支持的 Harness 运行时。')
            env = {k: v for k, v in os.environ.items() if not re.search(r'KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|^DSH_|^MDCG_', k, re.I)}
            env.update(ELECTRON_RUN_AS_NODE='1', LINGSHU_DSH_CLI=str(self.service.paths()[1]))
            proc = await asyncio.create_subprocess_exec(str(self.service.paths()[0]), '--expose-internals',
                str(BASE / 'external_mcp.cjs'), '--probe', env=env, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, limit=2*1024*1024,
                **({'creationflags': 0x08000000} if os.name == 'nt' else {'start_new_session': True}))
            tree = ProcessTree(proc.pid)
            output, _ = await asyncio.wait_for(proc.communicate(json.dumps(self.spec(name)).encode()), 20)
            if len(output) <= 2*1024*1024:
                body = json.loads(output)
                if proc.returncode == 0 and body.get('ok') and isinstance(body.get('tools'), list):
                    result.update(ok=True, code='CONNECTED', tools=body['tools'], server=body.get('server'))
        except asyncio.TimeoutError:
            result['code'] = 'MCP_TIMEOUT'
        except (OSError, ValueError, RuntimeError, HTTPException):
            pass
        finally:
            if tree:
                tree.close()
            if proc and proc.returncode is None:
                if os.name != 'nt':
                    import signal
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                else:
                    proc.kill()
                await proc.wait()
            self.checking.discard(name)
            self.tasks.discard(task)
        entry['check'] = result
        self.write()
        return result


def routes(get_service):
    router = APIRouter(prefix='/tools', route_class=PrivateValidationRoute)

    @router.get('')
    async def listing():
        tools = get_service().tools
        return [tools.public(name) for name in sorted(tools.entries)]

    @router.put('')
    async def save(request: ConnectionInput):
        service = get_service()
        async with service.lock:
            return service.tools.save(request)

    @router.post('/{name}/check')
    async def check(name: str):
        return await get_service().tools.check(name)

    @router.patch('/{name}')
    async def enable(name: str, request: EnabledInput):
        service = get_service()
        async with service.lock:
            service.tools.ensure_idle()
            entry = service.tools.get(name)
            if request.enabled and not (entry.get('check') or {}).get('ok'):
                raise HTTPException(409, '请先检查连接成功，再启用。')
            entry['enabled'] = request.enabled
            service.tools.write()
            return service.tools.public(name)

    @router.delete('/{name}')
    async def delete(name: str):
        service = get_service()
        async with service.lock:
            service.tools.ensure_idle()
            service.tools.get(name)
            service.tools.entries.pop(name)
            service.tools.write()
            (service.root / f'tool-{name}.dpapi').unlink(missing_ok=True)
            return {'ok': True}

    return router
