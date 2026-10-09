"""Read-only startup diagnostics. No model/network request is made."""
import argparse
import asyncio
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import tempfile
from version import VERSION

BASE = Path(__file__).resolve().parent


async def inspect():
    checks = []
    def add(name, ok, detail):
        checks.append({'name':name, 'ok':bool(ok), 'detail':detail})
    add('Python', sys.version_info[:2] == (3,13), f'{sys.version.split()[0]}；本版已验证 Python 3.13。')
    add('操作系统', os.name == 'nt', '本版支持 Windows。')
    packages_ready = True
    for line in (BASE / 'requirements.txt').read_text('utf-8').splitlines():
        if '==' not in line or line.startswith('#'):
            continue
        package, expected = line.strip().split('==', 1)
        try:
            actual = importlib.metadata.version(package)
            ok = actual == expected
        except importlib.metadata.PackageNotFoundError:
            actual, ok = '未安装', False
        packages_ready &= ok
        if not ok:
            add(package, False, f'当前 {actual}，需要 {expected}；请运行首次安装.cmd。')
    add('Python 依赖', packages_ready, '锁定依赖齐全。' if packages_ready else '请运行首次安装.cmd 修复环境。')
    try:
        from dependencies import resolve
        resolve()
        add('世界模型与记忆引擎', True, '固定源码及摘要校验通过。')
    except Exception as exc:
        add('世界模型与记忆引擎', False, str(exc))
    if packages_ready:
        from agent import AgentService, SettingsInput
        with tempfile.TemporaryDirectory(prefix='lingshu-doctor-') as temporary:
            service = AgentService(Path(temporary), 1)
            try:
                data = Path(os.environ.get('LINGSHU_WORKBENCH_DATA', BASE / 'data'))
                settings_file = data / 'agent/settings.json'
                if settings_file.exists():
                    settings = SettingsInput(**json.loads(settings_file.read_text('utf-8')))
                    service.settings.update(settings.model_dump(exclude={'api_key','clear_key'}))
                service.key_file = data / 'agent/key.dpapi'
                status = await service.status(force=True)
                add('Harness 配置', status['ready'], status['diagnostic'])
            except Exception:
                add('Harness 配置', False, '本地模型设置无效，请在模型设置中重新保存。')
            finally:
                await service.close()
    return {'version':VERSION, 'network_or_model_requested':False,
            'ok':all(check['ok'] for check in checks), 'checks':checks}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='检查灵枢启动环境，不发起模型请求。')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    result = asyncio.run(inspect())
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f'灵枢环境检查 {VERSION}\n')
        for check in result['checks']:
            print(f"{'通过' if check['ok'] else '待处理'} · {check['name']}：{check['detail']}")
        print('\n此检查不验证网络或账号额度；未配置模型时仍可手动运行实验。')
    sys.exit(0 if result['ok'] else 1)
