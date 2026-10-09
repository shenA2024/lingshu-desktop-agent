# DeepSeek Harness 实际集成

2026-10-09。安装版 0.2.0-rc.2，build `04f392c9ddd144fa426da2045178797da6db6c11`；安装资源和原有配置未修改。

## 实际启动

`agent.py` 使用安装版 Electron Node 执行本项目 `harness_runner.cjs`，调用 `dsh-desktop-host/lib/cli.js` 公开导出 `runDesktopCli(runtimeDir, supportDir)`。动态导入不会触发 CLI 的 import.meta.main 条件，故显式调用；运行时与包管理器仍由安装版 CLI 管理。

使用项目独立 DSH_HOME、固定 workspace 和 lingshu-agent profile，组合 dsh-base 与 dsh-headless。首轮不传 session id，从 JSONL 获取真实 id；续聊使用 `--session-id`，cwd 保持相同。未知 id 不会被偷偷换成新会话。

用户消息通过 stdin 传入 `--json -`，不拼接 shell。stderr 不保存，thinking 事件被丢弃。文本为步骤提交事件，final 为完整答案；非零退出即使有 final 也标失败并保留答案。Windows Job Object 的 KILL_ON_JOB_CLOSE 负责关闭轮次进程树。重启后未完成轮次标为 interrupted。

## 模型与工具

deepseek-flash／deepseek-v4-pro，thinking=enabled，reasoningEffort=high/max。本机 `.dsh/.credentials.yaml` 只读取 DEEPSEEK_API_KEY 引用，不复制整份凭据或迁移原文件。独立密钥为 Windows 用户级 DPAPI 密文，不返回 API、不拼入命令行或 patch。账号登录型路由、自定义供应商未接入。

独立 overlay 禁用 shell、任意文件、网络、技能、委派和持久目标工具，插入本地 dsh-mcp-client；提供六个实验／记忆工具。服务端创建实验时即登记所属轮次，停止本轮会请求停止本轮已启动且仍运行的实验，无需等候工具结果送达，不影响手动或其他会话实验。

其他客户端可在连接页复制 Cordis patch；`- insert:` 为本安装版接受的插件插入格式。

## 真实验收

隔离实验台 8797，DeepSeek Flash，高强度，沿用用户选择的本机模型凭据。

1. 模型实际调用 run_scene，perturbation、4 步，返回 `0e6ecf32bd19`。
2. 查询同一 id：completed、4 步、11/12 命中、1 次异常；回答与引擎字段一致。
3. 模型调用 recall，结果含同一 id 和 memory_id 的实际摘要。
4. 同一 Harness 会话在服务重启后成功继续回答原结果。
5. 另一真实模型轮次发起 120 步实验 `7faf9318f104`，停止 Agent 后在第 2 步取消。

`artifacts/agent-real-validation.json`：8 项全部通过，无伪造模型文本或工具请求。`tests/test_agent.py` 的夹具仅用于协议／生命周期回归，单独记录。

2026-10-08 的空白 home 验证曾因 MISSING_CREDENTIAL 只完成工具发现；此历史缺口已由上述真实验收补全。

## 当前实现：实验归属与配置验证（旧开发编号 0.3.1）

每轮 Harness 子进程携带 LINGSHU_AGENT_TURN_ID；MCP 桥将其作为 X-Lingshu-Turn-Id 传给本地服务。服务端在创建实验时登记归属，取消不再依赖工具结果送达；停止后的轮次无法再创建实验。内部标识不进入模型工具参数。

真实模型实验 d43ac1ab2876 已验证该环境传递及查询／召回链路。迟到结果／创建的时序用明确协议夹具和真实世界实验回归，不把夹具算作模型证据。

成功验证绑定模型、强度、运行时版本／文件修订、凭据修订信息。保存在 validations 表中，旧会话的成功状态不会验证新配置。仅支持 0.2.0-rc.2；安装和凭据存在检查不等于网络／账号请求成功。
