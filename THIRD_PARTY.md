# 上游版本、资源与许可证

## Lingshu

- 官方来源：<https://github.com/FuRongJun-1999/lingshu>
- 固定提交：212d4691ded095eb52fb23439cafac4d499ca8bd（2026-10-09 更新，旧版缓存保留）。
- 官方提交归档 SHA-256：d24783336f337d61798ba0cdd96dbd953cac66e1ea8ba2dcfad531d9490e4938。
- 外置归档目录：lingshu-<commit>，通过 sys.path 导入原生 SceneSimulator、UnifiedWorldModel 和 brain_store。
- 官方 pyproject.toml 存在，但本轮采用固定完整源码归档，以保证世界模拟资源和 brain 适配器与基准一致；未假设 PyPI 上同名包是官方发布。
- MIT；外置归档 LICENSE 保持原文，演示包附 licenses/lingshu-MIT.txt。
- 未携带先前 PR #14 水平关系修正，未改动任何研究 checkout。该历史贡献独立于本轮，链接：<https://github.com/FuRongJun-1999/lingshu/pull/14>。

## dsh-memory

- 官方来源：<https://github.com/FuRongJun-1999/dsh-memory>
- 固定提交：297e0b2a0482180092c8ddb480386ea4bd544bb6；package.json 版本 0.8.1。
- 官方提交归档 SHA-256：d3984995296184f5f19e286dffd2db21328196c6dab96f315b1d31fc0102efd6。
- Python MCP 入口 python -X utf8 -m md_cg.mcp_server，使用包根 PYTHONPATH。保留 utf8_boot.py、package.json、LICENSE 与 md_cg，不能仅复制 Python 包子目录。
- 零第三方 Python 依赖；完整归档包含 npm 插件源码等材料，但本实验不安装或运行 npm 插件。
- MIT；外置归档 LICENSE 保持原文，演示包附 licenses/dsh-memory-MIT.txt。

## 安装与完整性

dependencies.lock.json 固定提交和官方归档摘要。bootstrap.py 校验下载摘要、拒绝越界路径和符号链接，再在外置目录原子放置解压源码及清单。dependencies.py 启动前核对资源、文件摘要与额外文件，不回退旧 vendor 或补丁版本。网络失败可使用另一个外置缓存，已有路径不会被重置或覆盖。

完整上游源码仅存在外置缓存与迁移前私有备份，未包含在新演示包或建议提交清单中。Python HTTP 服务依赖按 requirements*.txt 锁定；pip 保留各包自带许可证。

## DeepSeek Harness

- 官方来源：<https://github.com/deepseek-ai/deepseek-harness>。
- 本机安装版 0.2.0-rc.2，build 04f392c9ddd144fa426da2045178797da6db6c11，buildDirty=false。
- 只参考界面形态并调用实际 dsh CLI；读取安装包中的 dsh-mcp-client 文档与 schema 核对接口，未修改安装资源，未复制其 UI、图标或代码到本实验台。
- 真实模型发起实验、查询同一 id、核对结果、召回摘要、重启续聊和停止均已验证，见 DSH_INTEGRATION.md。

界面图标为项目自身简易 SVG，无外部字体或 CDN。手动实验无需模型；对话通过本机 Harness 调用模型 API。
