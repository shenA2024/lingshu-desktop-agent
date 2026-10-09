# 参与开发

请先查看 README 的当前能力范围与 VERSIONING.md 的版本规则。问题和改进建议可在 GitHub Issues 提交；修改源码可通过 Pull Request 提交。

## 本地开发

使用 Windows、Python 3.13、PowerShell。安装开发依赖并运行回归：

```powershell
.\setup.ps1 -Dev -Python python
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

手动实验不需要模型。验证对话链路时需自行安装 DeepSeek Harness 0.2.0-rc.2 并配置模型凭据。不要将自己的 `data/`、API 密钥、原始会话、日志或备份提交至仓库；报告问题前删除其中的个人信息。

## 修改与验证

- 对话、实验生命周期与数据变化需运行相关回归。
- 界面修改保持三种主题的布局，欢迎区居中，并排入口等宽等高；检查桌面与窄屏。
- 不把协议夹具结果表述为真实模型请求，不把预设实验的边界覆盖命中表述为通用能力。
- 上游版本通过 `dependencies.lock.json` 锁定；更新提交与摘要时，保留版权声明并重跑世界模型与记忆回归。

## 构建体验包

```powershell
python .\scripts\build_release.py
python .\scripts\build_release.py --verify
```

输出位于 `dist/`，使用显式文件白名单，附 ZIP SHA-256 和逐文件清单。GitHub Release 采用 `v<version>` 标签；体验版标记为 prerelease。发布前确认标签、`version.py` 与包内清单版本一致。
