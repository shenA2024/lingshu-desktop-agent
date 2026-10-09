"""Resolve protected settings for one explicitly enabled MCP connection."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from agent import protect


def main():
    config, name, executable = sys.argv[1:]
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', name):
        raise ValueError('Invalid connection name')
    path = Path(config)
    entry = json.loads(path.read_text('utf-8'))[name]
    if not entry['enabled']:
        raise ValueError('Connection is disabled')
    secret_file = path.parent / f'tool-{name}.dpapi'
    secret = json.loads(protect(secret_file.read_bytes(), decrypt=True)) if secret_file.exists() else {'env': {}, 'headers': {}}
    spec = {k: entry[k] for k in ('transport', 'command', 'args', 'cwd', 'url')} | secret
    env = {k: v for k, v in os.environ.items() if not re.search(r'KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|^DSH_|^MDCG_', k, re.I)}
    cli = Path(executable).parent / 'resources/app.asar/dsh/node_modules/@deepseek-ai/dsh-desktop-host/lib/cli.js'
    env.update(ELECTRON_RUN_AS_NODE='1', LINGSHU_DSH_CLI=str(cli), LINGSHU_MCP_SPEC=json.dumps(spec))
    child = subprocess.Popen([executable, '--expose-internals', str(Path(__file__).with_name('external_mcp.cjs'))],
                             env=env, stdin=sys.stdin.buffer, stdout=sys.stdout.buffer, stderr=subprocess.DEVNULL,
                             **({'creationflags': 0x08000000} if os.name == 'nt' else {}))
    try:
        return child.wait()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


if __name__ == '__main__':
    sys.exit(main())
