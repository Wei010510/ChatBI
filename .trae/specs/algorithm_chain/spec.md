# 算法问答链路 - 产品需求规格（Spec）

## 概述

- **摘要**：基于 `docs/SDD-算法应用.md`（v3.0），落地 ChatBI 的 S1~S8 问数链路：理解 → 模板快道 → 检索 → 规划 → 生成 SQL（含 lint）→ 执行 → 出表出图 → 解读，由 LangGraph 固定状态机编排，四名智能体 + 四个规则节点，三个出口（answer / clarify / reject）。
- **目的**：让用户用自然语言问数，系统自动选出表/列/口径、生成只读 SQL、执行、出表出图并给一句话解读；零行业资源也能跑，拒答率可控。
- **目标用户**：业务同学（通过后端 API 间接使用本链路）；本 Spec 不涉及前端页面。

## 目标

- 实现 S1~S8 全链路，固定编队、固定条件边、不做 ReAct 自主调度。
- 三类出口（answer / clarify / reject）形状与 `ChainResult` 完全一致，互斥规则可校验。
- S5 lint 自检回炉（≤2 轮）、S6 执行回炉（≤1 次）、超时不重试，失败码语义清晰。
- 资源分层：L0 唯一硬依赖，口径词典/实体别名/模板/示例均为可选增强包，缺失不拒答。
- 算法不直连数据库，只依赖注入的 `QueryRunner` / `CacheStore` / `ResourceProvider` 协议。

## 非目标

- ❌ 不做真实数据库连接（`QueryRunner` 用 Mock 实现，供算法侧单测）。
- ❌ 不做后端服务、API 路由、存储表、部署（属后端 Spec 范围）。
- ❌ 不做前端页面、交互、图表渲染（属前端 Spec 范围）。
- ❌ 不设计向量存储 / pgvector（生产向量召回由后端实现；本步检索用关键词 / Mock）。
- ❌ 不做登录鉴权、权限中台、归因预测、仪表盘。
- ❌ 不做流式响应、不做多轮会话持久化（checkpointer 用内存 Mock 即可）。
- ❌ SDD 明确「不做」的内容（如饼图、智能选图、模型自行决定重试）一律不做。

## 背景与上下文

- 技术栈已写死：Python 3.11 + LangGraph + LiteLLM（OpenAI 兼容 API，env 配置，不绑厂商）。
- 链路契约（`ChatState` / `query_spec` / `ChainResult` / `QueryRunner` / `CacheStore` / `ResourceProvider`）以 `docs/SDD-算法应用.md` §7、§9 为准。
- 算法代码落点：`backend/app/agent/`（目录树见 SDD 总览 §7 / 后端 §1），包含 `graph.py` / `state.py` / `llm.py` / `nodes/` / `prompts/`。
- 修改顺序固定：算法 → 后端 → 前端 → 总览；本 Spec 只动算法。

## 功能需求

- **FR-1 链路骨架**：用 LangGraph `StateGraph` 构建 S1~S8 八个节点，条件边写死（三个出口、S2→S6 短路、S6→S5 回跳一次），无调度智能体、不做 ReAct。
- **FR-2 S1 理解（Planner·理解）**：LLM 小模型，`temperature=0`，结构化输出 `intent_spec`（指标 / 维度 / 过滤 / 时间窗 / 对比五类槽位）；只翻译不判断；四类范围问题（写操作 / 明细导出 / 库外 / 超时段）用关键词硬拦截，命中直接 `reject`。
- **FR-3 S2 模板快道**：纯规则，拿 `intent_spec` 槽位签名比对模板骨架；三者全满足（槽位齐全 / 每槽落具体列 / 口径无歧义）才算命中 → 填 SQL 跳 S6；未命中继续 S3，绝不拒答。同一问题精确重复时查 `CacheStore`。
- **FR-4 S3 检索**：捞四类弹药（表字段 / 口径 / 实体别名 / 典型复杂需求示例）；表/列/口径/实体 → S4，示例 → S5 few-shot；检索为空不报错。示例由后端 `resources.exemplars(question)` 提供（向量召回 + 形态重排，向量不可用时降级关键词）。
- **FR-5 S4 规划（Planner·规划，唯一拍板者）**：从 Evidence + L0 选表选列（必过存在性校验），定聚合公式（优先 L1，缺则推断标 `degraded`），展开实体约束，定时间窗与对比期；三档判定 `reachable` ∈ {answer, clarify, reject}；输出 `plan` + `query_spec`。澄清候选来自 Evidence，不要求事先登记字典。
- **FR-6 S5 生成 SQL + lint（Coder）**：LLM 强模型，`temperature=0`；按 `plan` + `plan.tables` 的「表→列清单」（取自 L0，写进 prompt）+ few-shot 生成单条只读 `SELECT`/`WITH`；lint 五条（单条语句 / 只读 / 表白名单=plan.tables / 列归属按 L0 列清单（聚合不套子查询）/ 强制 LIMIT）；不过带报错原文回炉，≤2 轮，仍不过 → `sql_generate_failed`。
- **FR-7 S6 执行**：调用注入的 `QueryRunner.run(sql, params, timeout_ms, max_rows)`；`error_code` 分流：`SQL_FAILED`/`SQL_REJECTED` → 带 message 回 S5 重写一次，二次失败 → `sql_execute_failed`；`QUERY_TIMEOUT` → `reject(timeout)` 不重试；空结果（`rows=[]`）仍 `answer` 出空表。
- **FR-8 S7 出表 + 图**：列名换业务名（plan 业务名兜底 L0 注释），行原样；形状检查记 `validation.warnings` 不 reject；`chart_spec` 只出 `bar`/`line`，判定顺序：空结果 → 两期对比 → 时间序列 → 类别维度（含排名）→ 单标量，命中即停；无匹配默认 `bar`，无非数值列 `chart=null`。
- **FR-9 S8 解读（Writer）**：LLM 中档模型；输入 question + query_spec + rows 摘要（≤20 行）+ chart_spec + validation.warnings + plan.degraded；输出一句 ≤60 字 narrative，只能引用输入数字，不推算不归因；`rows=[]` 不调用，`narrative=""`；模型失败用规则模板兜底。
- **FR-10 三出口与 ChainResult**：`action` ∈ {answer, clarify, reject} 互斥；`result` = {columns, rows, chart, narrative, truncated}；`clarify` = {clarify_id, question, options, allow_free_text, missing}；`reject` = {reason_code, message, suggestions, retryable}；`trace` 每步 {node, elapsed_ms, note}。
- **FR-11 拒答码**：`out_of_scope` / `detail_export` / `no_data` / `write_op`（业务，retryable=false）；`intent_parse_failed` / `sql_generate_failed` / `sql_execute_failed` / `timeout`（技术，retryable=true）。
- **FR-12 缓存写回**：仅 `action=answer` 且 `rows` 非空时 `CacheStore.put`，只存 `query_spec` / `sql` / `chart_spec`，不存 rows/narrative；`clarify`/`reject`/空结果不写。
- **FR-13 资源降级**：L1/模板/示例/别名任一缺失，链路照常走完，口径按列注释推断标 `degraded=true`，不拒答；只有 L0 缺失才无法工作。
- **FR-14 LLM 接入**：LiteLLM 统一封装 `chat_json()` / `chat_text()` / `embed()`，模型档位按任务配置（S1/S4 小模型、S5 强模型、S8 中档、Embedding 独立），env 配置 BASE_URL/API_KEY/MODEL。
- **FR-15 智能体上下文边界**：每名智能体只读 `ChatState` 中自己职责相关的字段，不接触他人 prompt；只通过 `ChatState` 交接，不互相对话。
- **FR-16 依赖注入**：`runner` / `cache_store` / `resources` 通过 `graph.invoke(config={"configurable": {...}})` 注入，不进 `ChatState`、不进 checkpointer。

## 非功能需求

- **NFR-1 零资源可用**：除 L0 外所有增强包缺失时，S1~S8 必须能完整走通并出表出图（C 档验收）。
- **NFR-2 拒答率可控**：C 档下除「数据里确实没有」外不出现拒答；「字典没登记」永不构成拒答理由。
- **NFR-3 可复现**：S1/S4/S5 `temperature=0`，同输入同输出。
- **NFR-4 算法不碰库**：算法模块不 import 任何数据库驱动，不持有连接串；只消费注入协议的返回值。
- **NFR-5 无死循环**：lint ≤2 轮、执行回炉 ≤1 次、超时不重试；禁止模型自行决定重试。
- **NFR-6 可观测**：每步产出 `trace` 记录 {node, elapsed_ms, note}。
- **NFR-7 可单测**：每个节点可独立调用并断言 `ChatState` 字段变化；Mock `QueryRunner`/`CacheStore`/`ResourceProvider` 可注入。

## 约束

- **技术**：Python 3.11、LangGraph、LiteLLM；不引入 LangChain 全家桶、不引入数据库驱动。
- **业务**：不做前端、不做后端服务/存储/部署、不做向量存储；只交付 `backend/app/agent/` 模块及其内部测试。
- **依赖**：`QueryRunner` / `CacheStore` / `ResourceProvider` 由后端实现，本步用 Mock；LLM API 需 env 配置（可指向测试模型或 Mock）。

## 假设

- L0 结构通过注入的 `ResourceProvider.l0()` 获取，本步用固定 Mock 数据。
- 模板 / 示例 / 口径词典文件格式参照 SDD §4，本步可用最小 Mock 文件或内存字典。
- `ChatState` 用 LangGraph 的 TypedDict 状态，checkpointer 用内存 `MemorySaver` 即可。
- 后端 SDD 定义的 `QueryResult` 字段（columns/rows/row_count/truncated/elapsed_ms/error_code/message）由 Mock 返回。

## 验收标准

### AC-1：链路骨架与固定编队
- **类型**：`rule`
- **Given**：算法模块已安装依赖
- **When**：加载 `graph.py` 构建的 LangGraph 图
- **Then**：图中存在且仅存在 8 个节点（understand/template/retrieve/plan/gen_sql/execute/present/narrate），节点名与 SDD §7.1 一致；条件边包含 S2→S6 短路、S6→S5 回跳、三个出口
- **Pass Condition**：节点清单与边清单与 SDD §1.2 mermaid 图完全对应
- **Evidence**：`graph.get_graph().nodes` 与 edges 的断言输出

### AC-2：ChatState 字段完整
- **类型**：`rule`
- **Given**：`state.py` 中 `ChatState` TypedDict
- **When**：对照 SDD §7.2 字段表逐项检查
- **Then**：所有字段（session_id/question/history/intent_spec/evidence/plan/query_spec/sql/lint_*/sql_error/retry_count/columns/rows/truncated/validation/chart_spec/narrative/action/result/clarify/reject/trace 等）齐全且类型正确
- **Pass Condition**：字段集合与 SDD §7.2 完全一致，无多余字段
- **Evidence**：`TypedDict` 定义与字段对照表

### AC-3：ChainResult 形状与互斥
- **类型**：`rule`
- **Given**：链路跑完返回 `ChainResult`
- **When**：分别触发 answer / clarify / reject 三种出口
- **Then**：`action` 三选一；answer 时 result 非空且 clarify/reject 为 null；clarify 时 clarify 非空且 result/reject 为 null；reject 时 reject 非空且 result/clarify 为 null；result 内部字段为 {columns, rows, chart, narrative, truncated}
- **Pass Condition**：三种出口形状与 SDD §7.4 完全一致
- **Evidence**：三种出口的样例输出 JSON

### AC-4：S1 理解只翻译不判断
- **类型**：`rule`
- **Given**：输入一个普通数据问题
- **When**：S1 节点执行
- **Then**：产出 `intent_spec`（五类槽位），不产出 `reachable` 判定；四类范围问题（如「把 GMV 改成 0」「导出所有订单明细」「竞品销量」「2020 年数据」）直接返回对应 `reject` reason_code
- **Pass Condition**：普通问题不被 S1 拒答；四类范围问题被 S1 正确拦截
- **Evidence**：S1 单元测试用例输出

### AC-5：S2 模板快道命中与未命中
- **类型**：`rule`
- **Given**：模板库含「单期单指标聚合」骨架
- **When**：输入「昨天华东 GMV」（槽位齐全可落列）
- **Then**：`template_hit=true`，产出 `query_spec`+`sql`，跳过 S3~S5 直达 S6
- **And When**：输入含模板无对应骨架的问题（如同比）
- **Then**：`template_hit=false`，继续 S3，不拒答
- **Pass Condition**：命中时跳过 S3~S5；未命中时继续且不拒答
- **Evidence**：S2 命中/未命中两组测试的节点执行轨迹

### AC-6：S4 是唯一拍板者
- **类型**：`rule`
- **Given**：S1/S2/S3 均未做可答性判定
- **When**：S4 执行
- **Then**：只有 S4 设置 `reachable` ∈ {answer, clarify, reject}；选表选列均来自 Evidence 或 L0 真实存在对象；近似可答时 `degraded=true` 仍 answer
- **Pass Condition**：reachable 仅由 S4 写入；近似场景走 answer 而非 reject
- **Evidence**：S4 单元测试（含近似可答用例）

### AC-7：S5 lint 五条与回炉
- **类型**：`rule`
- **Given**：Coder 生成 SQL
- **When**：SQL 含写操作 / 多语句 / 引用 plan.tables 外的表 / 列归属错误 / 无 LIMIT
- **Then**：lint 返回对应错误，带回 Coder 重写；连续 2 轮不过 → `reject(sql_generate_failed)`
- **Pass Condition**：五类违规各被 lint 检出；第 3 轮仍不过时 reason_code=sql_generate_failed
- **Evidence**：S5 lint 五类违规测试 + 回炉上限测试

### AC-8：S6 执行分流与空结果
- **类型**：`rule`
- **Given**：Mock QueryRunner 可配置 error_code
- **When**：返回 SQL_FAILED 首次 → 回 S5 重写；二次仍失败 → sql_execute_failed；返回 QUERY_TIMEOUT → reject(timeout) 不重试；返回 rows=[] → answer 空表
- **Then**：行为与 SDD §9.3 完全一致
- **Pass Condition**：四种 error_code 场景的出口与重试次数正确
- **Evidence**：S6 四场景测试输出

### AC-9：S7 图表判定顺序与只出 bar/line
- **类型**：`rule`
- **Given**：不同形状的 QueryResult
- **When**：S7 执行
- **Then**：判定顺序为空结果→两期对比→时间序列→类别维度(含排名)→单标量；chart.type 仅 bar/line；单标量 x_field=null；空结果 chart=null；占比类仍 bar
- **Pass Condition**：六种形状的 chart_spec 与 SDD §8 表完全一致
- **Evidence**：S7 六形状测试的 chart_spec 输出

### AC-10：S8 解读不编造
- **类型**：`rule`
- **Given**：rows 非空
- **When**：S8 执行
- **Then**：narrative 只引用输入中出现的数字，≤60 字，不含归因/建议；rows=[] 时 narrative=""
- **Pass Condition**：narrative 中所有数字均来自输入 rows；空结果 narrative 为空串
- **Evidence**：S8 单元测试（数字溯源断言）

### AC-11：资源降级不拒答
- **类型**：`rule`
- **Given**：ResourceProvider 返回空 L1/模板/示例/别名，仅 L0 有数据
- **When**：跑完整链路
- **Then**：链路走通 answer，plan.degraded=true，无 reject
- **Pass Condition**：C 档（零增强包）下完整链路出 answer
- **Evidence**：零资源端到端测试输出

### AC-12：算法不直连数据库
- **类型**：`rule`
- **Given**：算法模块全部源码
- **When**：grep 数据库驱动 import 与连接串
- **Then**：无 `psycopg`/`sqlalchemy`/`asyncpg` 等驱动 import，无硬编码连接串；SQL 执行仅通过注入的 `runner`
- **Pass Condition**：grep 零匹配数据库驱动
- **Evidence**：grep 命令输出

### AC-13：失败码语义
- **类型**：`rule`
- **Given**：各失败场景
- **When**：触发对应失败
- **Then**：`sql_generate_failed` 仅来自 S5 lint 两轮不过；`sql_execute_failed` 仅来自 S6 回炉一次仍失败；`timeout` 不重试；业务类 reject retryable=false，技术类 retryable=true
- **Pass Condition**：8 个 reason_code 的来源与 retryable 与 SDD §5.3 表一致
- **Evidence**：失败码映射测试

### AC-14：缓存写回条件
- **类型**：`rule`
- **Given**：Mock CacheStore
- **When**：answer 且 rows 非空 → put 被调用；clarify/reject/空结果 → put 不被调用
- **Then**：put 内容仅含 query_spec/sql/chart_spec，不含 rows/narrative
- **Pass Condition**：写回条件与内容与 SDD §7.5 一致
- **Evidence**：CacheStore 调用记录断言

### AC-15：智能体上下文边界
- **类型**：`rubric`
- **Dimension**：上下文隔离清晰度
- **Scale**：1-5
- **Anchors**：1 = 智能体间互相可见全部 state，无边界；3 = 部分隔离但有越权读取；5 = 每名智能体 prompt 仅引用自身职责字段，Writer 看不到 SQL/库，Planner·理解不接触 rows
- **Pass Threshold**：>= 4
- **Evidence**：各 agent prompt 文件的输入字段清单审查

## 开放问题

- [ ] LLM 模型三元组（BASE_URL/API_KEY/MODEL）本步用真实测试模型还是 Mock？（建议用 Mock LLM 保证单测稳定，集成测试再连真实 API）
- [ ] S5 lint 的「列归属」校验是否需要完整 SQL 解析器（如 sqlglow），还是正则足够？（建议引入 sqlglow 做 AST 校验，更可靠）
- [x] 模板库与示例库本步用 Mock 内存数据，还是读真实 `semantics/` 文件？→ 已定：读真实 YAML，单测用 `MockResourceProvider` 注入最小样例。
