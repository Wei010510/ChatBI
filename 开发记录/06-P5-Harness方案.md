# 06·P5 Harness方案

> 写代码前先落地 Harness：每次开聊带上项目总说明和硬规则；开发按 **算法 → 后端 → 前端** 三轮，用 Trae 的 `/spec` 生成规格、任务和验收；Skill 留到测试阶段再做。

**官方参考**：[规则与 AGENTS.md](https://docs.trae.cn/ide_rules) · [Plan / Spec / Goal](https://docs.trae.cn/ide_built-in-workflows) · [Skills](https://docs.trae.cn/ide_skills)

---

## 1. 这几层分别解决什么问题

| 叫什么 | 可以把它理解成 | 文件放哪 | 什么时候给 AI 看 | 它管什么 |
| :--- | :--- | :--- | :--- | :--- |
| 📋 **项目总说明** | 这个项目怎么合作 | 根目录 `AGENTS.md` | 每次开聊都带上 | 读哪些设计文档、这一轮做到哪算完、先改文档再改代码 |
| 🚫 **硬规则** | 不能碰的红线 | `.trae/rules/project_rules.md` | 每次开聊都带上 | 用什么技术、什么绝对不能做 |
| 📝 **Spec** | 这一轮的规格、任务和验收 | `.trae/specs/<任务名>/` 下的 `spec.md`、`tasks.md`、`checklist.md` | 用 Trae 的 `/spec` 生成；写代码时点名这一轮 | 这一轮做到哪算完，不要掺进下一轮 |
| 🛠 **Skill** | 反复会做、每次重讲容易漏的固定操作 | 开发阶段先不建 | 测试环节再加 | 见第 6 节 |

**`/spec` 使用说明**

- `/spec` 在 **TraeCode 编程智能体**里用，内置 Chat 用不了。
- 输入后会生成上面三份文件并停住等确认。
- 确认前可改文档或用话改，确认后按任务列表执行。
- ⚠️ 不要一次把整个系统丢给 `/spec`。

> 若根目录 `AGENTS.md` 带不进对话，把同样内容放到 `.trae/rules/`；以实测为准，不要两份各写一套。

---

## 2. 需要创建的文件

```text
1  AGENTS.md
2  .trae/rules/project_rules.md
3  .trae/specs/          # 由 `/spec` 按任务名生成
4  docs/                 # 已有 PRD、三份 SDD、测例
```

> 代码目录按三份 SDD 里已画好的结构来。Harness 不另起一套。

---

## 3. 项目总说明（`AGENTS.md`）

写短。只讲「怎么一起干活」，**不抄技术方案**。设置里打开「将 AGENTS.md 包含在上下文中」。

**建议写入这些要点**：

- 这是通用 ChatBI；电商大促只是第一包验收数据和问法，不要做成只能服务某一岗位。
- 动手前只认：`docs/PRD.md`、`docs/SDD-前端.md`、`docs/SDD-后端.md`。总览只当地图，不当链路依据。
- 接到任务，对上当前这一轮 `.trae/specs/<任务名>/`。只做这一轮任务，做完就停。没有对应 spec 时，先 `/spec` 生成、人看过再写代码。
- 文档和代码打架：先改 SDD 或这一轮 spec，再改代码。
- 改完列出动了哪些文件，以及怎么在界面或接口上点一遍。

**不要写**：接口字段表、八步细节、某张业务表 DDL（那些在 SDD / 本轮 spec 里）。

---

## 4. 硬规则（`.trae/rules/project_rules.md`）

只写**碰了架构就会歪**的红线。`alwaysApply: true`。

页面有几张、八步怎么走、字段长什么样，一律回对应 SDD，这里不抄。

> **和总说明的分工**：总说明管「先读什么、这一轮做到哪算完」；硬规则管「用什么栈、几条硬边界、绝对别做什么」。
>
> 故意从 SDD 里抽几条进硬规则，不是再讲一遍设计，而是因为硬规则每次开聊都会带上，SDD 只有点名才读；抽的是 AI 最容易另起炉灶的那几条。

| 块 | 红线 |
| :--- | :--- |
| **技术栈** | 前端 React + Vite + TypeScript、后端 FastAPI 单服务；算法 LangGraph，不要另起一套栈 |
| **三条边界** | 算法不直连库，无字典也要能跑；已存报表只读快照，不重查不重跑算法 |
| **存储与模型** | PostgreSQL（本地 Docker；生产推荐 Supabase）；LLM/Embedding 使用商业化 OpenAI 兼容 API，环境变量配置；不绑厂商、不本地部署模型 |
| **明确不做** | 完整登录权限中台、从零搭仪表盘、归因预测、上 K8s |

---

## 5. `/spec`：产出什么，三步盖完 SDD

编程智能体里输入 `/` 选 Spec，或直接 `/spec`（内置 Chat 用不了）。Trae 会在 `.trae/specs/<任务名>/` 生成三份文件并停住等人确认：

| 文件 | 作用 |
| :--- | :--- |
| `spec.md` | 文档：这一轮做什么 |
| `tasks.md` | 任务清单 |
| `checklist.md` | 验收清单 |

确认前可改；确认后按任务执行。Spec 不会像硬规则那样每次开聊自动带上。⚠️ 不要一次把整个系统丢进一次 `/spec`。

本项目固定三步（**顺序不能倒**）：算法 → 后端 → 前端。每步把下面话术贴进 `/spec`，人审过再确认执行；checklist 过了再开下一步。总览只当地图。

> **跨文档分工**：检索怎么用、如何降级归算法；文件和向量放哪、怎么部署归后端。



### 📘 第一步 · 算法

```text
/spec
请基于 docs/SDD - 算法应用.md，为本项目「算法问答链路」生成 Spec。
覆盖该文档本版要落地的内容；方案写明不做的不要做。
总览只当地图；冲突以 docs/SDD - 算法应用.md 为准。
无真库时允许 Mock 执行器与检索降级；不要做真连库、页面、另设计向量存储。
```


### � 第二步 · 后端

```text
/spec
请基于 docs/SDD - 后端.md，为本项目「后端服务」生成 Spec。
覆盖该文档本版要落地的所有内容；方案写明不做的不要做。
总览只当地图；冲突以 docs/SDD - 后端.md 为准。
算法链路以 docs/SDD - 算法应用.md 为准，本步不要重做算法内部步骤。
不要做前端页面。
```


### � 第三步 · 前端

```text
/spec
请基于 docs/SDD - 前端.md，为本项目「前端页面」生成 Spec。
覆盖该文档本版要落地的内容；方案写明不做的不要做。
总览只当地图；冲突以 docs/SDD - 前端.md 为准。
接口与返回体以后端 SDD、算法 SDD 的 ChainResult 为准，不要另发明接口或链路。
```

# 6. Skill：开发不做，测试再做

开发阶段规格用 /spec，写代码按本轮 tasks.md 推进，不另建 Skill。

三轮都能从提问走到结果后，再建测试验收 Skill：
- 依据：docs/测例.md（T01–T13） + docs/SDD-算法应用.md §10。
- 只验收：结果类型、是否编数、澄清/拒答是否符合现行算法方案；不改代码、不改 SDD。
- 测例原文与算法 SDD 冲突时以算法 SDD 为准（如 T09 不强制澄清、T10 不一律按「超字典」拒答）。

---

## 7. AICoding
总说明和硬规则开着。第 5 节三份 Spec 已生成并审过之后，按顺序三次指定 Spec 开发（一次只做一份，做完再开下一份）。仓库里对应目录：
- 算法：.trae/specs/algorithm-chain/
- 后端：.trae/specs/backend-service/
- 前端：.trae/specs/frontend-pages/

### 第一次·算法
```text
先读 .trae/specs/algorithm-chain/ 下的 spec.md、tasks.md、checklist.md，以及 docs/SDD - 算法应用.md。
只实现这一份 Spec 里的任务，做完就停，不要做后端接口和前端页面。
改完列出动了哪些文件。
```

### 第二次·后端
```text
先读 .trae/specs/backend-service/ 下的 spec.md、tasks.md、checklist.md，以及 docs/SDD - 后端.md。
只实现这一份 Spec 里的任务，做完就停，不要重做算法内部步骤，不要做前端页面。
改完列出动了哪些文件。
```

### 第三次·前端
```text
先读 .trae/specs/frontend-pages/ 下的 spec.md、tasks.md、checklist.md，以及 docs/SDD - 前端.md。
只实现这一份 Spec 里的任务，做完就停，不要另发明接口或返回体。
改完列出动了哪些文件。
``` 


