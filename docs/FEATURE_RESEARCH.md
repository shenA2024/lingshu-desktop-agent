# 灵枢 0.0.2：功能参考与后续方向

核实日期：2026-10-09。产品文档和远端主分支会变化；以下是阅读到的公开内容，不是对所有功能的实机验收。运行时仍锁定 Harness 0.2.0-rc.2 和原有世界模型、记忆依赖。

## 参考了什么

| 项目 | 核实到的能力 | 灵枢适合借鉴的部分 |
| --- | --- | --- |
| [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) | 插件组成的运行时；Web/桌面交互；技能、MCP、终端；[插件管理](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/client/ui-plugin-manager/README.md)支持管理已安装与官方扩展，按包规格安装；[智能体团队](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/agent-team.md)为实验功能，包含队员、持久邮箱、任务依赖和任务板。 | 先做可检查、可启停的工具连接，再建立扩展生命周期、兼容性、权限与团队任务状态。插件管理不等于所有社区扩展已有经过审核的市场。 |
| [ZCode 文档](https://zcode.z.ai/cn/docs) | 任务与文件管理、目标模式、浏览器自动化、Memory、自动化、Remote/Bot；[MCP 接入](https://zcode.z.ai/cn/docs/mcp-services)；[子智能体](https://zcode.z.ai/cn/docs/subagents)支持通用与 Explore 角色及用户级自定义 Beta。 | 工作台组织、明确的工具目录、长任务进度、任务与产物的关联。子智能体委派和持久团队仍需分别设计。 |
| [WorkBuddy 简介](https://www.workbuddy.cn/docs/workbuddy/Overview) | 自主规划执行、文档/表格/PPT 产物、本地文件操作、多任务、项目、专家、技能、连接器与资料库；官方文档导航还有多人多 Agent 协作。 | 通用任务、文件产物预览、连接器与资料整理。办公产物需要真正的文件生成与验收工具链。 |
| Codex 当前本机会话 | 可观察到项目/会话管理、worktree、文件与终端面板、评审和协作工具入口。 | 保留任务上下文、审阅变更、让执行过程和产物可检查。OpenAI Docs 的 features/multi-agent/plugins 页面在此次搜索并实际访问后均返回 403，因此没有对其最新市场与团队开放范围作发布结论。 |
| [VS Code 用户界面](https://code.visualstudio.com/docs/editing/getting-started/userinterface) | 官方文档介绍编辑区、主/次侧栏、活动栏、状态栏和面板，以及分组、命令面板、标签与窗口布局。 | 采用侧栏分组、可收起区域、清晰选中状态和快捷键；保留灵枢居中的欢迎区与简洁布局。文件树、编辑器多标签和终端停靠留到相应功能实际存在时再加入。 |

## TUI 与酒馆的边界

DeepSeek Harness 当前主分支已有 [移除 TUI 的实施记录](https://github.com/deepseek-ai/deepseek-harness/blob/master/.agents/notes/archived/simplification/2026-08-04-remove-tui-package.md)，归档日期为 2026-09-04：`packages/ui/tui` 已删除。当前 CLI README 中的 `--profile tui` 是“假设该 profile 已安装”的语法示例，并非仍然随包提供的产品。持久 PTY 终端、一次性 CLI 与完整 TUI 是不同能力。

[Lingshu 上游](https://github.com/FuRongJun-1999/lingshu)公开 README/文件树中没有查到酒馆接入实现。作者那句“忘记完善酒馆功能”的原始出处尚未核实。

不过，[dsh-memory README](https://github.com/FuRongJun-1999/dsh-memory)的 v0.8.0 记录明确提到 `state_atlas` 的全角色世界书与酒馆 worldbook JSON 导出。它证明公开项目存在世界书导出线索，不能据此认定已有完整 SillyTavern 插件、角色卡导入、多角色对话或双向会话同步。此次没有更新灵枢锁定的记忆依赖，也没有把这项导出标成灵枢现有功能。

## 本轮落地与下一步

0.0.2 实现会话置顶、归档、恢复与分类搜索；中英文界面和下一轮回复语言；统一的下拉弹层；12–20 的基础字号调节；通用 MCP 服务管理、实际连接检查、工具发现和模型调用。保留三种主题、居中欢迎区与等宽快捷入口。

下拉交互参考了 [Harness PopupSelect](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/client/ui-commands/src/client/PopupSelectView.tsx) 与 [Radix Select](https://www.radix-ui.com/primitives/docs/components/select) 的公开实现/文档：方向键、Home/End、输入搜索、Enter 选择、Escape/Tab/外部点击关闭、选中标记、滚动与视口避让。本项目使用原生 JavaScript 的独立实现，不引入 React 或复制这些项目的源码。

流畅度优先做即时点击反馈、减少重复绘制、140 ms 的透明度/位移过渡和稳定布局。字体调整通过 CSS 比例生效，避免拖动滑块时重建世界场景；系统要求减少动态效果时关闭过渡。实际样本见 [验证说明](../VALIDATION.md)，不承诺所有硬件达到同样帧率。

建议后续顺序：

1. 项目与资料收纳、文件产物预览、几个经过验证的通用 MCP 接入示例。
2. 世界书导入导出：先核实格式并完成实际酒馆导入验收，再考虑聊天同步。
3. 可管理的扩展目录：安装、版本兼容、权限、停用、卸载、更新与失败恢复。
4. 智能体团队：任务依赖、队员状态、消息传递、取消、资源限额与产物归属。

灵枢目前是可以运行的本地 Agent 工作台，还没有达到上述产品的完整功能范围。当前不包含内置插件市场、智能体团队、完整酒馆接入、内置通用文件编辑器或独立 EXE 安装器。通过用户启用的外部 MCP 可以扩展能力，范围取决于具体服务。
