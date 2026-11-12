# 算法问答链路 - 实现计划（tasks.md）

> 依赖：[spec.md](./spec.md)。每个任务含测试要求（rule / rubric），完成前必须自验通过。

## Task 1：工程脚手架与依赖
- **Status**：`completed`
- **Priority**：high
- **Depends On**：None
- **Description**：
  - 在 `algorithm/` 下建包：`__init__.py`、`graph.py`、`state.py`、`llm.py`、`config.py`、`protocols.py`、`lint.py`、`exceptions.py`、`run.py`、`prompts/`、`nodes/`、`tests/`。
  - `backend/pyproject.toml` 加依赖：`langgraph`、`litellm`、`sqlglot`（SQL AST 校验）、`pydantic`、`pytest`、`pytest-asyncio`。**禁止** `psycopg`/`sqlalchemy`/`asyncpg` 等数据库驱动。
  - `config.py`：从 env 读 `LLM_BASE_URL`/`LLM_API_KEY`/`MODEL_SMALL`/`MODEL_STRONG`/`MODEL_MID`/`EMBED_MODEL`/`SQL_TIMEOUT_MS`/`MAX_ROWS`，提供默认值。
- **Acceptance Criteria Addressed**：AC-12
- **Test Requirements**：
  - `rule` TR-1.1：`pyproject.toml` 依赖清单不含任何数据库驱动包；`grep -r "import psycopg\|import sqlalchemy" algorithm` 零匹配。
- **Notes**：`backend/` 根目录若已有 pyproject 则合并，否则新建。

## Task 2：状态与数据模型（state.py + exceptions.py）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 1
- **Description**：
  - `ChatState` TypedDict：字段与 SDD §7.2 完全一致（session_id/question/history/intent_spec/evidence/plan/query_spec/sql/lint_ok/lint_error/lint_round/sql_error/retry_count/columns/rows/truncated/validation/chart_spec/narrative/action/result/clarify/reject/trace）。
  - 数据类：`IntentSpec`（5 槽位）、`Evidence`（四类候选）、`Plan`（tables/columns/formula/time_window/compare/few_shot/degraded/reachable）、`QuerySpec`、`ChainResult`（§7.4）、`Clarify`、`Reject`。
  - `RejectCode` 枚举：8 个码（业务 4 + 技术 4）及 retryable 映射。
  - `ValidationWarning`、`ChartSpec`（type: bar|line, x_field, series）。
- **Acceptance Criteria Addressed**：AC-2, AC-13
- **Test Requirements**：
  - `rule` TR-2.1：`ChatState` 字段集合与 SDD §7.2 逐项 diff 为零。
  - `rule` TR-2.2：`RejectCode` 8 个值的 retryable 与 SDD §5.3 一致。
- **Notes**：用 Pydantic v2 BaseModel 做数据类（后端已用），ChatState 用 TypedDict（LangGraph 要求）。

## Task 3：协议与 Mock（protocols.py）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 1
- **Description**：
  - 定义 `QueryRunner` Protocol：`run(sql, params, timeout_ms, max_rows) -> QueryResult`（QueryResult: columns/rows/row_count/truncated/elapsed_ms/error_code/message）。
  - 定义 `CacheStore` Protocol：`get(key) -> CacheEntry | None`、`put(key, entry)`。
  - 定义 `ResourceProvider` Protocol：`l0() -> L0Schema`、`l1()`、`templates()`、`exemplars(question: str = "")`、`aliases()`（均可选返回）。
  - Mock 实现：`MockQueryRunner`（可配置 error_code/rows）、`MemoryCacheStore`、`MockResourceProvider`（可开关各类资源）。
- **Acceptance Criteria Addressed**：AC-8, AC-11, AC-14
- **Test Requirements**：
  - `rule` TR-3.1：`MockQueryRunner` 四种 error_code（NONE/SQL_FAILED/SQL_REJECTED/QUERY_TIMEOUT）可配置且返回正确 QueryResult。
  - `rule` TR-3.2：`MockResourceProvider` 可独立开关 L1/模板/示例/别名，关闭时对应方法返回空。

## Task 4：LLM 封装（llm.py）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 1
- **Description**：
  - 封装 LiteLLM：`chat_json(model, messages, temperature) -> dict`（强制 JSON 输出）、`chat_text(model, messages, temperature) -> str`、`embed(model, texts) -> list[list[float]]`。
  - 模型档位从 config 取（small/strong/mid/embed）；temperature 默认 0。
  - 异常统一捕获，返回结构化错误（不抛到链路外层）。
  - 支持 `MockLLM`（预置响应）供单测，通过 env 开关切换。
- **Acceptance Criteria Addressed**：NFR-3
- **Test Requirements**：
  - `rule` TR-4.1：`chat_json` 非法 JSON 时返回错误而非抛异常；temperature 固定 0。
  - `rule` TR-4.2：`MockLLM` 可按消息前缀返回预设响应。

## Task 5：四个智能体 Prompt（prompts/）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 2
- **Description**：
  - `planner_understand.md`：S1，输入 question+history，输出 intent_spec JSON；明确「只翻译不判断」。
  - `planner_plan.md`：S4，输入 intent_spec+evidence+l0，输出 plan+query_spec+reachable；明确「唯一拍板者，近似可答优先」。
  - `coder.md`：S5，输入 plan+few_shot，输出 SQL；明确「单条只读 SELECT」。
  - `writer.md`：S8，输入 question+query_spec+rows 摘要+chart+warnings+degraded，输出 ≤60 字 narrative；明确「只引用输入数字」。
  - 每个 prompt 只引用自身职责字段，不出现越权读取（如 writer 不读 sql）。
- **Acceptance Criteria Addressed**：AC-15
- **Test Requirements**：
  - `rubric` TR-5.1：上下文隔离；scale 1-5；anchors 1=互相可见全部 state, 3=部分越权, 5=各 prompt 仅引用自身字段；threshold >=4；evidence: prompt 文件输入字段清单审查。

## Task 6：S1 理解节点（nodes/understand.py）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 2, Task 4, Task 5
- **Description**：
  - 调 Planner·理解（chat_json，temperature=0）抽 intent_spec。
  - 四类范围关键词硬拦截：写操作（INSERT/UPDATE/DELETE/修改/删除）、明细导出（导出明细/导出行）、库外（竞品/友商/外部）、超时段（数据时间范围外）→ 直接 reject 对应 reason_code。
  - intent_spec 非法枚举 → 重试 1 次，仍非法 → reject(intent_parse_failed)。
- **Acceptance Criteria Addressed**：AC-4, AC-13
- **Test Requirements**：
  - `rule` TR-6.1：普通问题产出 intent_spec 且不设 reachable。
  - `rule` TR-6.2：四类范围问题各返回正确 reject reason_code（write_op/detail_export/out_of_scope/no_data）。
  - `rule` TR-6.3：非法 intent_spec 重试 1 次后 reject(intent_parse_failed)。

## Task 7：S2 模板快道节点（nodes/template.py）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 2, Task 3
- **Description**：
  - 纯规则，不调 LLM。拿 intent_spec 槽位签名比模板骨架。
  - 命中条件：槽位齐全 + 每槽落具体列 + 口径无歧义 → 填 SQL 模板，template_hit=true，query_spec+sql 写入 state，边跳 S6。
  - 未命中：template_hit=false，继续 S3，不拒答。
  - 精确重复问题：先查 CacheStore，命中则复用 query_spec+sql+chart_spec 跳 S6（不复用 rows）。
  - 模板加载时统一过一遍与 S5 同款 lint（lint.py）。
- **Acceptance Criteria Addressed**：AC-5
- **Test Requirements**：
  - `rule` TR-7.1：「昨天华东 GMV」类槽位齐全问题 → template_hit=true，state 含 sql，下一节点为 execute。
  - `rule` TR-7.2：含同比的问题 → template_hit=false，下一节点为 retrieve，无 reject。
  - `rule` TR-7.3：模板加载时违规 SQL 被 lint 拦截不入库。

## Task 8：S3 检索节点（nodes/retrieve.py）
- **Status**：`completed`
- **Priority**：medium
- **Depends On**：Task 2, Task 3
- **Description**：
  - 捞四类弹药：①表字段（L0 + 关键词）②口径（L1，缺则用列注释）③实体别名（aliases）④示例（`exemplars(question)`，后端向量召回后按形态重排）。
  - ①②③ → S4 evidence；④ → S5 few_shot。
  - 检索为空不报错，evidence 各字段为空列表。
  - 算法层不引入向量存储：向量召回由后端 `resources` 完成，不可用时后端降级关键词，算法只收示例对象。
- **Acceptance Criteria Addressed**：NFR-1
- **Test Requirements**：
  - `rule` TR-8.1：四类弹药缺失时 evidence 各字段为空，不抛异常。
  - `rule` TR-8.2：示例（④）只写入 plan.few_shot 字段，不写入 evidence 的 table/column/caliber/entity。

## Task 9：S4 规划节点（nodes/plan.py）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 2, Task 4, Task 5
- **Description**：
  - 调 Planner·规划（chat_json，temperature=0），输入 intent_spec+evidence+l0。
  - 选表选列必过存在性校验（只从 Evidence 或 L0 真实对象选）。
  - 聚合公式优先 L1，缺则按列名/注释推断标 degraded=true。
  - 展开实体约束（如江浙沪→IN 三省）。
  - 定时间窗与对比期。
  - 三档判定 reachable ∈ {answer, clarify, reject}；近似可答优先 answer。
  - 澄清候选从 Evidence 取，不要求登记字典。
  - 输出 plan + query_spec。
- **Acceptance Criteria Addressed**：AC-6
- **Test Requirements**：
  - `rule` TR-9.1：只有 plan 节点写入 state.reachable。
  - `rule` TR-9.2：选表/列不在 L0 或 Evidence 时被校验拒绝，回退或标 degraded。
  - `rule` TR-9.3：近似可答场景 reachable=answer 且 degraded=true。
  - `rule` TR-9.4：澄清时 clarify 候选来自 Evidence 字段。

## Task 10：SQL lint 规则（lint.py）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 2
- **Description**：
  - 用 sqlglot 解析 SQL AST，实现五条规则：
    1. 单条语句（只允许 1 条 SELECT/WITH）
    2. 只读（无 INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/CREATE）
    3. 表白名单（只能引用 plan.tables）
    4. 列归属（带前缀列按 L0 校验；单表作用域校验无前缀列；CTE/派生表/SELECT 别名豁免），聚合不套子查询
    5. 强制 LIMIT（无则补 max_rows）
  - 返回 `LintResult(ok: bool, errors: list[str])`。
- **Acceptance Criteria Addressed**：AC-7
- **Test Requirements**：
  - `rule` TR-10.1：五类违规 SQL 各被对应规则检出并返回 errors。
  - `rule` TR-10.2：合法 SQL 返回 ok=true 且补 LIMIT。

## Task 11：S5 生成 SQL 节点（nodes/gen_sql.py）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 2, Task 4, Task 5, Task 10
- **Description**：
  - 调 Coder（chat_text，temperature=0），输入 plan+few_shot+相关表列类型，产出 SQL。
  - 生成后调 lint.py；不过则把 lint errors 回填 Coder 重写，lint_round++。
  - 连续 2 轮不过 → reject(sql_generate_failed)。
  - 限制总轮次，禁止模型自行决定重试。
- **Acceptance Criteria Addressed**：AC-7
- **Test Requirements**：
  - `rule` TR-11.1：lint 不过时 lint_round 递增且 errors 回填 prompt。
  - `rule` TR-11.2：lint_round 达 2 仍不过 → reject(sql_generate_failed)，不再调 LLM。
  - `rule` TR-11.3：合法 SQL 一次通过，直接进 S6。

## Task 12：S6 执行节点（nodes/execute.py）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 2, Task 3
- **Description**：
  - 调用注入的 runner.run(sql, params, timeout_ms, max_rows)。
  - error_code 分流：
    - NONE → columns/rows/truncated 写入 state，进 S7
    - SQL_FAILED / SQL_REJECTED（首次）→ sql_error 写入，retry_count++，回 S5
    - SQL_FAILED / SQL_REJECTED（二次）→ reject(sql_execute_failed)
    - QUERY_TIMEOUT → reject(timeout)，不重试
  - 空结果 rows=[] → 仍 answer 进 S7（不 reject）。
- **Acceptance Criteria Addressed**：AC-8
- **Test Requirements**：
  - `rule` TR-12.1：四种 error_code 场景的下一节点与 reject reason 正确。
  - `rule` TR-12.2：retry_count 仅递增 1 次后走 reject。
  - `rule` TR-12.3：rows=[] 时不 reject，继续 S7。

## Task 13：S7 出表出图节点（nodes/present.py）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 2
- **Description**：
  - 列名换业务名（plan 业务名优先，兜底 L0 注释），rows 原样。
  - 形状检查（两期对比结构校验等）记 validation.warnings，不 reject。
  - chart_spec 判定顺序：空结果→两期对比→时间序列→类别维度(含排名)→单标量，命中即停。
  - type 仅 bar/line；单标量 x_field=null；空结果 chart=null；无匹配默认 bar；无非数值列 chart=null。
  - truncated 透传。
- **Acceptance Criteria Addressed**：AC-9
- **Test Requirements**：
  - `rule` TR-13.1：六种形状各产出正确 chart_spec（与 SDD §8 表一致）。
  - `rule` TR-13.2：chart.type 仅 bar 或 line，无 pie/scatter 等。
  - `rule` TR-13.3：单标量 x_field=null；空结果 chart=null。
  - `rule` TR-13.4：形状异常记 validation.warnings 且不 reject。

## Task 14：S8 解读节点（nodes/narrate.py）
- **Status**：`completed`
- **Priority**：medium
- **Depends On**：Task 2, Task 4, Task 5
- **Description**：
  - rows=[] 时不调 LLM，narrative=""。
  - rows 非空时调 Writer（chat_text），输入 question+query_spec+rows 摘要(≤20 行)+chart_spec+validation.warnings+plan.degraded。
  - 输出 ≤60 字，只引用输入数字。
  - LLM 失败用规则模板兜底（如「本期 {指标} 为 {值}」）。
- **Acceptance Criteria Addressed**：AC-10
- **Test Requirements**：
  - `rule` TR-14.1：rows=[] → narrative=""。
  - `rule` TR-14.2：narrative 中每个数字都能在输入 rows 或 chart 中找到来源。
  - `rule` TR-14.3：narrative 长度 ≤60 字。

## Task 15：图编排（graph.py）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 6, 7, 8, 9, 11, 12, 13, 14
- **Description**：
  - `StateGraph(ChatState)` 添加 8 个节点，名与 SDD §7.1 一致。
  - 条件边：S1→reject（范围问题）/S2；S2→S6（命中或缓存命中）/S3；S4→clarify/reject/S5；S5→S6（lint 过）/S5（回炉，≤2 轮）/reject(sql_generate_failed)；S6→S7/S5（回炉 1 次）/reject；S7→S8；S8→answer。
  - 用 `MemorySaver` checkpointer（不持久化）。
  - 注入 runner/cache_store/resources 走 `config={"configurable": {...}}`。
- **Acceptance Criteria Addressed**：AC-1
- **Test Requirements**：
  - `rule` TR-15.1：`graph.get_graph().nodes` 恰好 8 个且命名与 SDD §7.1 一致。
  - `rule` TR-15.2：边集合包含 S2→execute 短路、execute→gen_sql 回跳、三个出口。

## Task 16：入口与 ChainResult 组装（run.py）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 15
- **Description**：
  - `ask(question, session_id, history, runner, cache_store, resources) -> ChainResult`。
  - 调 graph.invoke，注入依赖。
  - 从 state 组装 ChainResult：action 三选一互斥；answer→result；clarify→clarify；reject→reject；trace 全程收集。
  - 缓存写回：仅 answer 且 rows 非空时 cache_store.put(query_spec/sql/chart_spec)。
  - 失败码 retryable 映射。
- **Acceptance Criteria Addressed**：AC-3, AC-13, AC-14
- **Test Requirements**：
  - `rule` TR-16.1：三种出口 ChainResult 形状互斥且与 SDD §7.4 一致。
  - `rule` TR-16.2：answer 且 rows 非空 → cache_store.put 被调用且仅含 query_spec/sql/chart_spec。
  - `rule` TR-16.3：clarify/reject/空结果 → cache_store.put 不被调用。
  - `rule` TR-16.4：reject 的 retryable 与 RejectCode 映射一致。

## Task 17：节点单元测试
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 6-14
- **Description**：
  - `tests/test_s1_understand.py` … `test_s8_narrate.py`，每个节点独立可调用，断言 state 字段变化。
  - Mock LLM / Mock QueryRunner / Mock ResourceProvider 注入。
  - 覆盖各 AC 的 rule 测试点。
- **Acceptance Criteria Addressed**：AC-4 ~ AC-10, AC-13
- **Test Requirements**：
  - `rule` TR-17.1：8 个节点测试文件全部存在且可独立运行（`pytest algorithm/tests/ -q` 通过）。

## Task 18：端到端测试
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 16, Task 17
- **Description**：
  - `tests/test_e2e_zero_resource.py`：仅 L0 有数据，跑完整链路 → answer，degraded=true，无 reject。
  - `tests/test_e2e_template_hit.py`：单期单指标问题 → S2 命中 → 跳过 S3~S5。
  - `tests/test_e2e_reject.py`：四类范围问题 + SQL 生成失败 + 执行失败 + 超时。
  - `tests/test_e2e_clarify.py`：多解读且结论不同 → clarify。
  - `tests/test_e2e_compare.py`：同比问题 → 两行对比表 + bar + x_field=period。
- **Acceptance Criteria Addressed**：AC-3, AC-5, AC-8, AC-9, AC-11, AC-13
- **Test Requirements**：
  - `rule` TR-18.1：零资源端到端用例返回 action=answer，rows 非空或空表，无 reject。
  - `rule` TR-18.2：模板命中用例的 trace 中不含 retrieve/plan/gen_sql 节点。
  - `rule` TR-18.3：同比用例 chart.x_field=="period"，rows 含 2 行。

