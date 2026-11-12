# 后端服务 - 验收清单（checklist.md）

> 对应 [spec.md](./spec.md) 的 20 条验收标准（AC-1 ~ AC-20）。实现完成后逐条勾选，全部通过才算本 Spec 验收完成。

---

## 一、分层与接口

- [x] **AC-1 分层与依赖边界** 〔rule〕
  - `api/` 只调 `services/`，不直连 `agent/`
  - `agent/` 无 psycopg/sqlalchemy import，不持连接串
  - `storage/` 不反向依赖其他层
  - **证据**：grep 输出 + 依赖图

- [x] **AC-2 12 个接口全部注册** 〔rule〕
  - POST /chat/ask、POST /chat/clarify
  - GET /sessions、GET /sessions/{id}/messages、DELETE /sessions/{id}、DELETE /sessions
  - POST /reports、GET /reports、GET /reports/{id}、PATCH /reports/{id}、DELETE /reports/{id}
  - GET /health
  - 统一前缀 /api
  - **证据**：`/openapi.json` paths 列表

- [x] **AC-3 统一响应包** 〔rule〕
  - 所有接口返回 `{code, message, data, trace_id}`
  - code=0 → data 非 null；code≠0 → data=null
  - **证据**：接口测试响应样例

- [x] **AC-4 ChainResult 透传与互斥** 〔rule〕
  - 后端只加 message_id/session_id、剥离 trace
  - answer → result 非空，clarify/reject 为 null
  - clarify → clarify 非空，result/reject 为 null
  - reject → reject 非空，result/clarify 为 null
  - clarify/reject 状态下 result 非空 → 500
  - **证据**：三种出口响应 JSON + 互斥校验测试

---

## 二、QueryRunner 与执行

- [x] **AC-5 QueryRunner 物理兜底 9 条** 〔rule〕
  - 只读角色 chatbi_ro
  - search_path=data，含 app./public. 前缀拒
  - 外层 LIMIT+1 截断，超 max_rows 标 truncated
  - statement_timeout 超时 → QUERY_TIMEOUT
  - 参数化，不拼 SQL
  - 只允许单条 SELECT（可含 WITH）
  - 写操作黑名单（INSERT/UPDATE/DELETE/DROP/ALTER/...）
  - data 表白名单（14 张表）
  - 禁明细查询
  - 违规 → SQL_REJECTED，不执行
  - **证据**：9 条违规 SQL 测试输出

- [x] **AC-6 QueryResult 归一化** 〔rule〕
  - columns 含 key/title/type（number/string/date）
  - 数值转 float/int；日期 ISO 字符串；null 保留
  - **证据**：归一化测试

- [x] **AC-7 失败分流** 〔rule〕
  - SQL_REJECTED / SQL_FAILED 首次 → 回炉一次
  - 二次失败 → sql_execute_failed
  - QUERY_TIMEOUT → reject(timeout) 不重试
  - 空结果 → answer 空表
  - **证据**：失败分流测试

---

## 三、缓存、元数据、资源

- [x] **AC-8 CacheStore 读写** 〔rule〕
  - get 未过期返回 {query_spec, sql, chart_spec}，过期 None
  - put upsert，写 expires_at
  - 不存 rows/narrative
  - **证据**：CacheStore 测试

- [x] **AC-9 L0 Introspection** 〔rule〕
  - 返回 {tables, columns, data_range, schema_version}
  - 含 14 张数仓表及列信息（列可空性 / 主外键 / 行数 / 采样值 / 注释齐全）
  - schema_version 变化触发重读
  - 读取失败 → 启动失败
  - **证据**：introspection 测试

- [x] **AC-10 资源降级** 〔rule〕
  - L1/模板/示例/别名全缺 → 启动成功
  - 问数链路走通，plan.degraded=true，无 reject
  - **证据**：零资源端到端测试

- [x] **AC-11 pgvector 自动降级** 〔rule〕
  - PGVECTOR_ENABLED=auto 且无 vector 扩展 → 启动不报错
  - S3 检索走 lexical 关键词
  - 有 `app.exemplar_embeddings` 时走向量召回：示例问句原文 top1 命中自身，向量不可用（key 缺失 / 维度不符）时 `vector_search` 返回空且不抛异常
  - **证据**：无 pgvector 环境启动日志 + 检索测试 + 16 条示例问句召回验证

---

## 四、报表与消息

- [x] **AC-12 报表只读快照** 〔rule〕
  - GET /api/reports/{id} 直接读 snapshot_* 组装 result
  - 不执行 SQL、不调算法
  - **证据**：报表打开测试（runner mock 未被调用）

- [x] **AC-13 报表存为约束** 〔rule〕
  - message_id 非 answer 或 rows 空 → 422 MESSAGE_NOT_QUERYABLE
  - 同名且 overwrite=false → 409 REPORT_NAME_EXISTS
  - chart_type 非 bar/line → 拒绝
  - **证据**：报表接口约束测试

- [x] **AC-14 存储表结构** 〔rule〕
  - sessions/messages/reports/semantic_cache/query_logs 五张表字段与 SDD §4 完全一致
  - messages 含 query_spec/sql/chart_spec/clarify_state 分列
  - reports 含 snapshot_columns/snapshot_rows/snapshot_truncated
  - **证据**：表结构对照 diff

- [x] **AC-15 澄清状态暂存** 〔rule〕
  - clarify_state = {clarify_id, original_question, missing, options, expires_at}
  - /chat/clarify 结构化补全调算法，不拼自然语言
  - 过期/不存在 → 409 CLARIFY_EXPIRED
  - **证据**：澄清流程测试

- [x] **AC-16 消息落库与 trace 剥离** 〔rule〕
  - user + assistant 两条消息入库
  - assistant.payload = ChainResult（不含 trace）
  - query_logs 含 sql/row_count/elapsed_ms/error_code/cached/trace
  - **证据**：落库数据断言

- [x] **AC-17 语义缓存写回条件** 〔rule〕
  - answer 且 rows 非空 → cache.put
  - clarify/reject/空结果 → 不 put
  - put 内容仅 query_spec/sql/chart_spec；source 标 template/generated
  - **证据**：缓存写回测试

---

## 五、部署与数据

- [x] **AC-18 Docker Compose 可启动** 〔rule〕
  - db/api/web 三容器 healthy
  - /api/health 返回 ok
  - 干净环境可完成一次问数
  - **证据**：compose ps + 问数 curl 结果

- [x] **AC-19 只读角色自检** 〔rule〕
  - DATABASE_RO_URL 角色非只读 → 启动失败
  - **证据**：启动自检测试

- [x] **AC-20 数据 seed 幂等** 〔rule〕
  - seed 两次行数与 3 个核心指标一致
  - app schema 不清空
  - **证据**：两次 seed 结果对比

---

## 验收结论

- [x] 全部 20 条 rule 通过 → 本 Spec 验收 **通过**
- 否则 → 退回实现阶段修复
