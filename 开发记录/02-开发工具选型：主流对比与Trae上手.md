# 02-开发工具选型：主流对比与Trae上手

---

## 结论

| 项 | 选择 |
| ---- | ---- |
| 主工具 | TraeCode（AI IDE） |
| 容灾 | Cursor |
| 原则 | 工具服从内容 |

下载 TraeCode，不要下成 TraeWork。官网：trae.cn

---

## 业内三种主流路线

### 路线一：AI IDE（Cursor、Trae）
编辑器与 Agent 做成同一套产品：补全、对话、多文件改仓在一个界面里完成。

| 代表 | 特点 |
| ---- | ---- |
| Cursor | 目前最主流的 AI 原生 IDE 之一；生态与资料成熟；上一期已用 |
| Trae（TraeCode） | 手感接近 Cursor；国内直连更友好；支持 Rules / Skills / AGENTS |

主路径就落在这一类。

### 路线二：VS Code + AI 插件

熟悉的 VS Code，再挂 Copilot 等插件。补全、轻对话强；整仓规格驱动、长时间 Agent 改仓，一体感通常弱于 AI IDE。

| 代表 | 特点 |
| ---- | ---- |
| GitHub Copilot 等 | 装在 VS Code 里即可用；深度 VibeCoding 往往不如专用 AI IDE |

### 路线三：终端 / CLI Agent（Claude Code、Codex）

以对话式 Agent 为主，在终端（或挂扩展）里读仓、改文件、跑命令。Harness / Skills 叙事可以很完整，但对网络、账号和操作习惯要求更高。

| 代表 | 特点 |
| ---- | ---- |
| Claude Code | Anthropic 系；Skills / 子 Agent 能力强；国内网络与账号成本更高 |
| Codex 等 | 偏 CLI / 云端任务；异步代写方便；本地仓录播跟做不如 IDE 直观 |

---

## 为什么选 TraeCode（路线一）
1. AI IDE 一体感 — 比「VS Code + 插件」更适合长时间规格驱动实操
2. 能涵盖核心能力 — Rules / Skills / AGENTS.md
3. 换新工具，但不绑高摩擦方案 — 相对 Cursor 有差异；又不必扛 Claude Code 一类 CLI 的网络与账号成本
4. 容灾清晰 — 同一仓库可切回 Cursor（同属路线一）

不是追榜单最强，而是选能稳定完成验收的主工具。

---

## TraeCode ≠ TraeWork
| | TraeCode | TraeWork |
| ---- | ---- | ---- |
| 是什么 | AI 原生 IDE | AI 原生工作台 |
| 形态 | 本地编辑器 + Agent | 网页 / 桌面 / 移动；Work / Code / Design |
| 本次 | 主开发环境 | 不作为主 IDE |
| 用途 | 开仓库、写代码、右侧智能体改项目 | 跨场景一句话派任务 |

---

