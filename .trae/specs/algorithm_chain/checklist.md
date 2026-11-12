# 算法问答链路 - 验收清单（checklist.md）

> 对应 [spec.md](./spec.md) 的 15 条验收标准（AC-1 ~ AC-15）。实现完成后逐条勾选，全部通过才算本 Spec 验收完成。
> `rule` = 二进制可验证；`rubric` = 评分制，需达到阈值。

---

## 一、链路骨架与契约

- [ ] **AC-1 链路骨架与固定编队** 〔rule〕
  - 图中恰好 8 个节点：`understand / template / retrieve / plan / gen_sql / execute / present / narrate`，命名与 SDD §7.1 一致
  - 条件边包含：S2→S6 短路、S6→S5 回跳一次、三个出口（answer / clarify / reject）
  - 无调度智能体、无 ReAct 自主调度
  - **证据**：`graph.get_graph().nodes` 与 edges 断言输出

- [ ] **AC-2 ChatState 字段完整** 〔rule〕
  - `ChatState` 字段集合与 SDD §7.2 完全一致，无多余字段
  - 包含：session_id / question / history / intent_spec / evidence / plan / query_spec / sql / lint_* / sql_error / retry_count / columns / rows / truncated / validation / chart_spec / narrative / action / result / clarify / reject / trace
  - **证据**：`TypedDict` 定义与字段对照表 diff 为零

- [ ] **AC-3 ChainResult 形状与互斥** 〔rule〕
  - `action` ∈ {answer, clarify, reject} 三选一互斥
  - answer → result 非空，clarify/reject 为 null
  - clarify → clarify 非空，result/reject 为 null
  - reject → reject 非空，result/clarify 为 null
  - result 内部 = {columns, rows, chart, narrative, truncated}
  - **证据**：三种出口样例输出 JSON

---

## 二、逐节点行为

- [ ] **AC-4 S1 理解只翻译不判断** 〔rule〕
  - 普通问题产出 `intent_spec`（五类槽位），不设 `reachable`
  - 写操作 → `write_op`；明细导出 → `detail_export`；库外 → `out_of_scope`；超时段 → `no_data`
  - **证据**：S1 单元测试用例输出

- [ ] **AC-5 S2 模板快道命中与未命中** 〔rule〕
  - 槽位齐全可落列 → `template_hit=true`，产出 query_spec+sql，跳过 S3~S5 直达 S6
  - 无对应骨架（如同比）→ `template_hit=false`，继续 S3，不拒答
  - **证据**：S2 命中/未命中两组测试的节点执行轨迹

- [ ] **AC-6 S4 是唯一拍板者** 〔rule〕
  - 只有 S4 写入 `reachable` ∈ {answer, clarify, reject}
  - 选表选列均来自 Evidence 或 L0 真实存在对象
  - 近似可答 → `degraded=true` 仍 answer
  - 澄清候选来自 Evidence，不要求登记字典
  - **证据**：S4 单元测试（含近似可答用例）

- [ ] **AC-7 S5 lint 五条与回炉** 〔rule〕
  - lint 五条各检出对应违规：单条语句 / 只读 / 表白名单 / 列归属（含无前缀列、CTE 豁免）/ 强制 LIMIT
  - lint 不过带 errors 回填 Coder 重写，lint_round 递增
  - 连续 2 轮不过 → `reject(sql_generate_failed)`，不再调 LLM
  - **证据**：S5 lint 五类违规测试 + 回炉上限测试

- [ ] **AC-8 S6 执行分流与空结果** 〔rule〕
  - `SQL_FAILED`/`SQL_REJECTED` 首次 → 回 S5 重写（retry_count++）
  - 二次失败 → `sql_execute_failed`
  - `QUERY_TIMEOUT` → `reject(timeout)`，不重试
  - `rows=[]` → 仍 answer 进 S7（不 reject）
  - **证据**：S6 四场景测试输出

- [ ] **AC-9 S7 图表判定顺序与只出 bar/line** 〔rule〕
  - 判定顺序：空结果 → 两期对比 → 时间序列 → 类别维度（含排名）→ 单标量，命中即停
  - `chart.type` 仅 `bar` 或 `line`
  - 单标量 → `x_field=null`；空结果 → `chart=null`；占比类仍 `bar`
  - 形状异常记 `validation.warnings`，不 reject
  - **证据**：S7 六形状测试的 chart_spec 输出

- [ ] **AC-10 S8 解读不编造** 〔rule〕
  - narrative 中每个数字都能在输入 rows 或 chart 中找到来源
  - 长度 ≤60 字，不含归因/建议
  - `rows=[]` → `narrative=""`，不调 LLM
  - **证据**：S8 单元测试（数字溯源断言）

---

## 三、资源、失败与边界

- [ ] **AC-11 资源降级不拒答** 〔rule〕
  - L1/模板/示例/别名全空，仅 L0 有数据 → 完整链路走通 answer
  - `plan.degraded=true`，无 reject
  - **证据**：零资源端到端测试输出

- [ ] **AC-12 算法不直连数据库** 〔rule〕
  - 无 `psycopg` / `sqlalchemy` / `asyncpg` 等驱动 import
  - 无硬编码连接串
  - SQL 执行仅通过注入的 `runner`
  - **证据**：grep 命令输出零匹配

- [ ] **AC-13 失败码语义** 〔rule〕
  - `sql_generate_failed` 仅来自 S5 lint 两轮不过
  - `sql_execute_failed` 仅来自 S6 回炉一次仍失败
  - `timeout` 不重试
  - 业务类（out_of_scope / detail_export / no_data / write_op）→ retryable=false
  - 技术类（intent_parse_failed / sql_generate_failed / sql_execute_failed / timeout）→ retryable=true
  - **证据**：失败码映射测试

- [ ] **AC-14 缓存写回条件** 〔rule〕
  - answer 且 rows 非空 → `cache_store.put` 被调用，内容仅含 query_spec / sql / chart_spec
  - clarify / reject / 空结果 → `cache_store.put` 不被调用
  - **证据**：CacheStore 调用记录断言

- [ ] **AC-15 智能体上下文边界** 〔rubric〕
  - 维度：上下文隔离清晰度
  - 阈值：>= 4 / 5
  - 每名智能体 prompt 仅引用自身职责字段；Writer 看不到 SQL/库；Planner·理解不接触 rows
  - **证据**：各 agent prompt 文件输入字段清单审查

---

## 验收结论

- [ ] 全部 14 条 rule 通过，1 条 rubric ≥ 4 → 本 Spec 验收 **通过**
- 否则 → 退回实现阶段修复
