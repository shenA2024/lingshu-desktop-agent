# 0.0.1 验证记录

日期：2026-10-09。验证环境：Windows、Python 3.13.15、DeepSeek Harness 0.2.0-rc.2、Edge。

当前产品正式编号为 **0.0.1**，功能集对应开发阶段旧编号 0.3.1。历史证据保留原编号，版本规则见 [VERSIONING.md](VERSIONING.md)。此处只列仓库包含的精选记录。

## 后端回归

29 项检查全部通过，覆盖世界模型与记忆、固定依赖完整性、stdio MCP、会话幂等与互斥、子进程清理、重启恢复、DPAPI 加密、正文搜索 / 删除、配置验证隔离、停止后迟到创建拒绝、实验归属、备份完整性 / 拒绝覆盖和真实记忆恢复。

`tests/test_agent.py` 等协议与生命周期检查使用明确的进程夹具，不能当作真实模型调用证据。

```powershell
.\setup.ps1 -Dev -Python python
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

历史运行日志：[stability-031-unittest.txt](artifacts/stability-031-unittest.txt)。日志首行的本机 Python 路径替换为通用 `python` 命令；结果未改写。

## 真实模型与备份

DeepSeek Flash、高强度，实际完成实验 `d43ac1ab2876`：4 步，边界覆盖命中 11/12。查询同一 id、召回同一摘要、MCP 实验归属和回答与引擎字段一致性通过。

切换未验证配置后重新标记为待验证；切回原配置保留该配置自己的成功记录。重启后配置验证和会话身份保留。

真实备份恢复到全新目录：1 个对话、1 个实验、1 条记忆笔记；实验轨迹逐项一致，笔记可由真实记忆引擎召回，恢复后的会话明确只读。

证据：[stability-031-real-validation.json](artifacts/stability-031-real-validation.json)。

此前另一轮真实模型验收验证了重启后同一 Harness 会话续聊，以及停止 Agent 后本轮 120 步实验在第 2 步取消。8 项检查全部通过，证据：[agent-real-validation.json](artifacts/agent-real-validation.json)。真实请求记录不包含凭据、原始运行时会话或私人对话。

## 浏览器与主题

- 70 项 Edge / Playwright 交互与布局检查通过，浏览器错误为 0。覆盖白天、夜晚、暖色，1440 / 1280 / 1024 / 390 宽度，正文搜索、模型状态、删除取消 / 确认、备份下载、恢复历史和新建会话。
- 2683 项文字与 SVG 配色检查通过，最低对比度 4.5678:1。覆盖六页面、设置分类和模型 / 删除 / 实验 / 帮助 / 实体窗口。
- 上述配色检查是已测范围的颜色检查，未包含完整辅助技术审计。

证据：[UI](artifacts/stability-031-ui-validation.json)、[配色](artifacts/stability-031-contrast-validation.json)，以及同目录的精选截图。README 中的主题截图来自实际应用，未经像素改写。

## 自动检查与边界

GitHub Actions 配置为 Windows / Python 3.13，安装锁定依赖后运行同一回归套件、JavaScript 语法与发布包清单检查。自动检查不运行真实模型请求，不能代替端到端模型验收。实际运行结果见仓库 Actions。

其他 Harness 版本、供应商、账号登录型路由、其他操作系统、附件、多用户、完整辅助技术审计和大规模长时间负载尚未验证。预测边界覆盖命中属于具体预设实验，不能解释为通用能力准确率。
