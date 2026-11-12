# 后端服务 - 实现计划（tasks.md）

> 依赖：[spec.md](./spec.md)。每个任务含测试要求，完成前自验通过。

## Task 1：核心基础设施（core/）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：None
- **Description**：
  - `core/config.py`：pydantic-settings 读 env（DATABASE_URL / DATABASE_RO_URL / DATABASE_META_URL / LLM_* / EMBEDDING_* / QUERY_TIMEOUT_MS=5000 / MAX_ROWS=1000 / CACHE_TTL_SECONDS=604800 / PGVECTOR_ENABLED=auto）。
  - `core/logging.py`：JSON 结构化日志，含 trace_id（contextvar）。
  - `core/exceptions.py`：AppException 基类 + HTTP 错误码映射（400/404/409/422/500），统一异常处理器。
  - `core/deps.py`：`get_current_user()` 恒返回 `{user_id: "demo"}`；`get_db()` 依赖。
- **Acceptance Criteria Addressed**：AC-2, AC-19
- **Test Requirements**：
  - `rule` TR-1.1：config 读取缺失 env 时有合理默认或明确报错。
  - `rule` TR-1.2：AppException 抛出后响应体为统一包格式且 code≠0。

## Task 2：Pydantic 模型（schemas/）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 1
- **Description**：
  - 统一响应 `ApiResponse[T] = {code, message, data, trace_id}`。
  - ChatAnswer = message_id + session_id + ChainResult（result/clarify/reject 互斥）。
  - 入参：ChatAskRequest / ChatClarifyRequest / ReportCreateRequest / ReportUpdateRequest。
  - 出参：SessionItem / MessageItem / ReportListItem / ReportDetail。
  - 序列化层校验：clarify/reject 状态下 result 非空 → 抛 500。
- **Acceptance Criteria Addressed**：AC-3, AC-4
- **Test Requirements**：
  - `rule` TR-2.1：三种 action 的 ChatAnswer 序列化形状与算法 §7.4 一致。
  - `rule` TR-2.2：clarify/reject 且 result 非空时序列化抛异常。

## Task 3：存储层（storage/）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 1
- **Description**：
  - ORM 模型：Session / Message / Report / SemanticCache / QueryLog，字段与 SDD §4 完全一致。
  - `storage/session.py`：SQLAlchemy engine + sessionmaker（DATABASE_URL）。
  - `storage/repository.py`：各表 CRUD（sessions/messages/reports/cache/query_logs），查询带 user_id='demo'。
  - Message.payload 存 ChainResult（不含 trace）；query_spec/sql/chart_spec/clarify_state 分列。
  - Report 存 snapshot_columns/snapshot_rows/snapshot_truncated + chart_spec/narrative + 溯源列。
- **Acceptance Criteria Addressed**：AC-14, AC-16
- **Test Requirements**：
  - `rule` TR-3.1：五张表字段与 SDD §4 逐项 diff 为零。
  - `rule` TR-3.2：Message 保存后 payload 不含 trace 字段。

## Task 4：数据库初始化 SQL（infra/init.sql）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：None
- **Description**：
  - 建 app / data schema；建 chatbi_ro 只读角色；GRANT USAGE + SELECT ON data.*。
  - 不建业务表（data 表由 seed/schema.sql，app 表由 ORM）。
  - 可选：条件创建 pgvector 扩展 + `app.exemplar_embeddings`（`vector(EMBED_DIM)` + HNSW，PGVECTOR_ENABLED 探测）。
- **Acceptance Criteria Addressed**：AC-14
- **Test Requirements**：
  - `rule` TR-4.1：执行 init.sql 后 app/data schema 存在，chatbi_ro 仅有 data 的 SELECT 权限。

## Task 5：QueryRunner + sql_guard（query/）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 1
- **Description**：
  - `query/sql_guard.py`：9 条物理兜底（只读连接、search_path=data、外层 LIMIT+1 截断、statement_timeout、参数化、单条 SELECT、写操作黑名单、data 表白名单=14 张表、禁明细）。
  - `query/runner.py`：`PgQueryRunner.run(sql, params, timeout_ms, max_rows) -> QueryResult`，用 DATABASE_RO_URL 连接，套 sql_guard，执行，归一化结果。
  - `query/models.py`：QueryResult（columns/rows/row_count/truncated/elapsed_ms/error_code/message），error_code ∈ {None, SQL_REJECTED, SQL_FAILED, QUERY_TIMEOUT}。
  - 归一化：列 key/title（注释优先）/type（number/string/date 映射），数值转 float/int，日期 ISO，null 保留。
- **Acceptance Criteria Addressed**：AC-5, AC-6, AC-7
- **Test Requirements**：
  - `rule` TR-5.1：9 条违规 SQL 各返回 SQL_REJECTED。
  - `rule` TR-5.2：合规 SELECT 正常返回 QueryResult，列类型映射正确。
  - `rule` TR-5.3：超 max_rows 时 truncated=true 且截断。

## Task 6：CacheStore（query/cache_store.py）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 3
- **Description**：
  - `PgCacheStore.get(key)`：未过期返回 {query_spec, sql, chart_spec}，否则 None。
  - `PgCacheStore.put(key, value)`：upsert 写 semantic_cache，含 l1_version/schema_version/template_version/source/expires_at。
  - TTL 默认 CACHE_TTL_SECONDS。
- **Acceptance Criteria Addressed**：AC-8, AC-17
- **Test Requirements**：
  - `rule` TR-6.1：put 后 get 能取回，过期后 get 返回 None。
  - `rule` TR-6.2：put 内容不含 rows/narrative。

## Task 7：Introspection（query/introspection.py）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 1
- **Description**：
  - `PgIntrospector.l0()`：用 DATABASE_META_URL（缺省回落 DATABASE_RO_URL）独立只读连接读 information_schema。
  - 返回 {tables, columns, data_range, schema_version}（tables=14 张数仓表及列信息，data_range=事实表日期列最早最晚）。
  - 进程内缓存，schema_version（列结构哈希）变化时重读；读取失败 → 抛启动致命异常。
- **Acceptance Criteria Addressed**：AC-9
- **Test Requirements**：
  - `rule` TR-7.1：l0() 返回含 14 张表及列信息的结构（列含类型 / 注释 / 可空 / 主外键 / 行数 / 采样值）。
  - `rule` TR-7.2：schema_version 变化时触发重读（缓存失效）。

## Task 8：资源加载（resources/）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 7
- **Description**：
  - `resources/provider.py`：ResourceProvider 实现，l0() 调 introspector，l1() 读 semantics/metrics.yaml（缺则空 dict），templates() 读模板文件，exemplars(question) 先走向量召回（`app.exemplar_embeddings` top_k=5）→ 按 exemplar_id 映射回 `exemplars.yaml` 完整对象 → 规则重排；向量不可用或未命中时降级 lexical，aliases() 读实体别名。
  - `resources/retrieval.py`：pgvector 探测（PGVECTOR_ENABLED=auto）、embed_texts、vector_search；不可用走 lexical；任一资源缺失不报错。
  - `semantics/embed_exemplars.py`：`python -m semantics.embed_exemplars` 增量摄取示例问句向量（维度校验 + 幂等 upsert）。
- **Acceptance Criteria Addressed**：AC-10, AC-11
- **Test Requirements**：
  - `rule` TR-8.1：metrics.yaml 不存在时 l1() 返回空，不抛异常。
  - `rule` TR-8.2：无 pgvector 时 exemplars() 走 lexical 返回关键词匹配结果。

## Task 9：数仓表与 seed（seed/）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 4
- **Description**：
  - `seed/schema.sql`：建 data schema 14 张表（7 维度 + 7 事实，见 SDD §5.2），字段与 SDD §5.2 一致。
  - `seed/seed.py`：`python -m seed.seed` 删 data 表 → 重建 → 导入 CSV → 校验行数 + 3 个核心指标（GMV/订单数/退款率）期望值；幂等；不清空 app schema。
  - `seed/data/*.csv`：最小可验证样例数据。
- **Acceptance Criteria Addressed**：AC-20
- **Test Requirements**：
  - `rule` TR-9.1：执行 seed 两次，行数与 3 个指标一致。
  - `rule` TR-9.2：seed 后 app schema 表数据不受影响。

## Task 10：会话/报表/问数服务（services/）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 3, Task 5, Task 6, Task 8
- **Description**：
  - `services/chat_service.py`：ask(question, session_id?) — 新建/取会话 → 读最近 6 轮历史 → 组装 runner/cache_store/resources → 调 `agent.ask()` → 落 user/assistant 消息 → trace 写 query_logs → answer 且 rows 非空时 cache.put → 返回 ChatAnswer。
  - `services/chat_service.py`：clarify(session_id, clarify_id, answer) — 取 clarify_state → 结构化补全调算法 → 清空 clarify_state → 返回 ChatAnswer；不存在/过期 → CLARIFY_EXPIRED。
  - `services/session_service.py`：list_sessions(limit) / get_messages(session_id) / delete_session(session_id) / delete_all_sessions()。
  - `services/report_service.py`：create_report(message_id, name, chart_type, overwrite) — 校验 message 为 answer 且 rows 非空（否则 MESSAGE_NOT_QUERYABLE）；同名处理；存快照；list_reports / get_report（只读快照）/ rename / delete。
- **Acceptance Criteria Addressed**：AC-4, AC-7, AC-12, AC-13, AC-15, AC-16, AC-17
- **Test Requirements**：
  - `rule` TR-10.1：ask 完整流程落库 user+assistant 消息，payload 不含 trace，query_logs 含 trace。
  - `rule` TR-10.2：answer 且 rows 非空时 cache.put 被调用；否则不调用。
  - `rule` TR-10.3：get_report 不调用 runner（mock 断言）。
  - `rule` TR-10.4：clarify 用结构化补全，不拼自然语言重理解。

## Task 11：API 路由（api/）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 2, Task 10
- **Description**：
  - `api/chat.py`：POST /chat/ask、POST /chat/clarify。
  - `api/sessions.py`：GET /sessions、GET /sessions/{id}/messages、DELETE /sessions/{id}、DELETE /sessions。
  - `api/reports.py`：POST /reports、GET /reports、GET /reports/{id}、PATCH /reports/{id}、DELETE /reports/{id}。
  - `api/health.py`：GET /health。
  - 统一前缀 /api，统一响应包包装。
- **Acceptance Criteria Addressed**：AC-2, AC-3
- **Test Requirements**：
  - `rule` TR-11.1：10 条路由全部注册，路径与方法与 SDD §2 一致。
  - `rule` TR-11.2：错误场景返回正确 HTTP 状态码与 code。

## Task 12：入口与启动自检（main.py）
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 11
- **Description**：
  - `main.py`：FastAPI app，注册路由 + 异常处理器 + CORS。
  - lifespan：建 app schema 表（ORM create_all）、L0 introspection 预热、pgvector 探测、只读角色权限自检（DATABASE_RO_URL 角色非只读 → 拒绝启动）。
- **Acceptance Criteria Addressed**：AC-1, AC-19
- **Test Requirements**：
  - `rule` TR-12.1：只读角色无写权限时启动失败并报错。
  - `rule` TR-12.2：正常启动后 /api/health 返回 ok。

## Task 13：口径词典与增强包（semantics/）
- **Status**：`completed`
- **Priority**：medium
- **Depends On**：None
- **Description**：
  - `semantics/metrics.yaml`：8 指标（GMV/支付订单数/AOV/转化率/退货率/退款率/退款金额占比/新客GMV占比）+ 同义词 + 维度。
  - `semantics/bootstrap.py`：`python -m semantics.bootstrap` 由 L0 生成 `*.draft.yaml` 草稿（模板、示例、别名），人工审核后手动转正为正式文件；不自动改正式增强包。
  - 模板文件与示例文件最小样例。
- **Acceptance Criteria Addressed**：AC-10
- **Test Requirements**：
  - `rule` TR-13.1：metrics.yaml 可被 resources.l1() 正确加载为指标字典。

## Task 14：Docker Compose 与部署文件
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 12
- **Description**：
  - `Dockerfile`：python:3.11-slim + uvicorn，拷贝 backend。
  - `docker-compose.yml`：db(postgres:16, volume pgdata, init.sql) / api(Dockerfile, 依赖 db health) / web(nginx:alpine + 前端 dist 占位)。
  - `.env.example`：全部变量含注释。
  - `nginx.conf`：静态资源 + /api 反向代理。
- **Acceptance Criteria Addressed**：AC-18
- **Test Requirements**：
  - `rule` TR-14.1：docker compose up 后三容器 healthy，/api/health 可达。

## Task 15：集成测试
- **Status**：`completed`
- **Priority**：high
- **Depends On**：Task 12, Task 9
- **Description**：
  - `tests/test_e2e_ask.py`：一次问数走通，返回 answer + 表 + 图 + 解读。
  - `tests/test_e2e_clarify.py`：澄清 → 提交 → 拿到 answer。
  - `tests/test_e2e_reports.py`：存报表 → 打开快照（不触发 runner）→ 改名 → 删除。
  - `tests/test_zero_resource.py`：无 L1/模板/示例/别名时问数返回 answer degraded。
  - `tests/test_reject.py`：写操作/明细/库外/超时段 → 对应 reject。
- **Acceptance Criteria Addressed**：AC-4, AC-7, AC-10, AC-12, AC-13, AC-15, AC-16, AC-17
- **Test Requirements**：
  - `rule` TR-15.1：端到端问数测试通过（可用 TestClient + Mock agent）。
  - `rule` TR-15.2：报表打开测试中 runner mock 未被调用。
