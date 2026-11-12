# 后端服务 - 产品需求规格（Spec）

## 概述

- **摘要**：基于 `docs/SDD-后端.md`（v3.0），落地 ChatBI 后端单体服务：FastAPI 入口 + 模块化分层（api/services/agent/resources/query/storage/core/schemas），提供 12 个 HTTP 接口，实现 QueryRunner 物理兜底与执行、CacheStore、L0 Introspection、资源加载（含 pgvector/lexical 降级）、会话/消息/报表/缓存/日志存储、Docker Compose 部署。
- **目的**：把算法链路（已由 `算法问答链路` Spec 落地在 `backend/app/agent/`）包成可运行的后端服务，负责「调算法、执行 SQL、落库、返回统一报文」。
- **目标用户**：前端页面（通过 HTTP API）；本 Spec 不涉及前端实现。

## 目标

- 12 个接口全部可用，统一响应包 `{code, message, data, trace_id}`。
- 算法不直连库：后端实现 `QueryRunner` / `CacheStore` / `ResourceProvider` 并注入 `agent/`。
- QueryRunner 物理兜底写死（只读角色、schema 隔离、行数上限、超时、参数化、单条 SELECT、写操作黑名单、表白名单、禁明细），旁路调用不得绕过。
- 存储 5 张 app 表（sessions/messages/reports/semantic_cache/query_logs）+ data schema 5 张数仓表。
- 资源分层：L0 硬依赖，口径词典/模板/示例/别名可选增强；pgvector 不可用时自动降级 lexical。
- 一条命令起服务（docker compose up），干净环境能完成一次问数。

## 非目标

- ❌ 不重做算法内部步骤（S1~S8 由 `agent/` 负责，本步只调用）。
- ❌ 不做自然语言理解、SQL 生成、口径判定（算法职责）。
- ❌ 不改算法产出的 SQL（只做物理兜底，不判口径）。
- ❌ 不做前端页面、交互、图表渲染。
- ❌ 不做流式响应、报表可视化编排、数据源管理界面、跨库联邦。
- ❌ 不做登录鉴权/权限中台/多租户（仅 `get_current_user()` 恒返回 demo）。
- ❌ SDD 明确「不做」的内容一律不做。

## 背景与上下文

- 技术栈：Python 3.11 + FastAPI + SQLAlchemy 2.0 + Pydantic v2 + psycopg 3 + PostgreSQL 16。
- 算法链路已在 `backend/app/agent/`，本步实现其周边：`query/`（执行/缓存/元数据）、`resources/`（资源加载）、`storage/`（ORM）、`services/`（编排）、`api/`（路由）、`core/`（配置/日志/异常/依赖）、`schemas/`（Pydantic）。
- 协议形状以 `docs/SDD-算法应用.md` §7.4（ChainResult）、§9.2（QueryRunner）、§9.4（CacheStore/ResourceProvider）为准。
- 修改顺序：算法 → 后端 → 前端 → 总览；本 Spec 只动后端。

## 功能需求

### 核心与分层
- **FR-1 入口与分层**：`main.py` 创建 FastAPI app，注册路由、异常处理器、lifespan（DB 初始化、L0 introspection 缓存、pgvector 探测）；目录结构与 SDD §1 一致；`api/` 只调 `services/`，不直连 `agent/`。
- **FR-2 配置与日志**：`core/config.py` 从 env 读 DATABASE_URL / DATABASE_RO_URL / DATABASE_META_URL / LLM_* / EMBEDDING_* / QUERY_TIMEOUT_MS / MAX_ROWS / CACHE_TTL_SECONDS / PGVECTOR_ENABLED；`core/logging.py` 结构化日志含 trace_id；`core/exceptions.py` 统一异常 → HTTP 错误码映射。
- **FR-3 鉴权预留**：`core/deps.py` 提供 `get_current_user()` 恒返回 `{user_id: "demo"}`；所有查询默认带 `user_id='demo'`。

### 接口层
- **FR-4 统一响应与错误码**：所有接口返回 `{code, message, data, trace_id}`；HTTP 错误码表与 SDD §2.5 一致（400/404/409/422/500）；`code` 非 0 时 `data=null`。
- **FR-5 `/api/chat/ask`**：入参 `{session_id?, question}`；缺 session_id 新建会话；`services/chat_service` 读最近 6 轮历史 → 组装 runner/cache_store/resources → 调 `agent.ask` → 落库 user/assistant 消息 → 剥离 trace 到 query_logs → 返回 ChatAnswer（message_id + session_id + ChainResult）。
- **FR-6 `/api/chat/clarify`**：入参 `{session_id, clarify_id, answer}`；按 clarify_id 取暂存 clarify_state，合成结构化补全调算法，不把答案拼回自然语言；clarify_id 不存在/过期 → 409 CLARIFY_EXPIRED。
- **FR-7 会话接口**：`GET /api/sessions?limit` 列表（按 updated_at 倒序）；`GET /api/sessions/{id}/messages` 拉消息（user 消息简形、assistant 消息完整 ChatAnswer）；`DELETE /api/sessions/{id}` 删除单条会话（连带消息，不存在 → 404 SESSION_NOT_FOUND）；`DELETE /api/sessions` 清空当前用户全部会话，返回 `deleted_count`。
- **FR-8 报表接口**：`POST /api/reports`（message_id 必须是 answer 且 rows 非空，否则 422；同名 409 可 overwrite；chart_type 只能 bar↔line）；`GET /api/reports?page&size`；`GET /api/reports/{id}` 只读快照（不执行 SQL、不调算法）；`PATCH` 改名；`DELETE`。
- **FR-9 `/api/health`**：返回 `{status: "ok"}`，供 Compose 探活。

### 运行期协议实现
- **FR-10 QueryRunner（PgQueryRunner）**：实现 `run(sql, params, timeout_ms, max_rows) -> QueryResult`；物理兜底 9 条（只读角色、search_path=data、外层 LIMIT+1 截断、statement_timeout、参数化、单条 SELECT、写操作黑名单、data 表白名单、禁明细），任一不过返回 SQL_REJECTED；结果归一化（列 key/title/type、数值 float/int、日期 ISO、null 保留）。
- **FR-11 失败分流**：SQL_REJECTED / SQL_FAILED → 算法回炉一次后仍失败 → sql_execute_failed；QUERY_TIMEOUT → reject(timeout) 不重试；空结果 → answer 空表。
- **FR-12 CacheStore（PgCacheStore）**：实现 `get/put` 读写 `app.semantic_cache`；只存 query_spec/sql/chart_spec，不存 rows/narrative；TTL 默认 7 天；cache_key 含 l1_version/schema_version/template_version。
- **FR-13 L0 Introspection（PgIntrospector）**：用 DATABASE_META_URL（缺省回落 DATABASE_RO_URL）独立只读连接读 information_schema；返回 {tables, columns, data_range, schema_version}；进程内缓存，schema_version 变化重读；读取失败 → 启动失败。
- **FR-14 资源加载（resources/）**：`l0()` 调 introspection；`l1()` 读 `semantics/metrics.yaml`（缺则空）；`templates()` 读模板文件；`exemplars(question)` 先向量召回（`app.exemplar_embeddings` top_k=5，按 exemplar_id 映射回 YAML 完整对象并规则重排），向量不可用或未命中时降级 lexical；`aliases()` 读实体别名；任一缺失不报错。

### 存储与数据
- **FR-15 ORM 模型（storage/）**：sessions / messages / reports / semantic_cache / query_logs 五张表，字段与 SDD §4 完全一致；messages.payload 存 ChainResult（不含 trace）；messages 单独列 query_spec/sql/chart_spec/clarify_state；reports 存 snapshot_columns/snapshot_rows/snapshot_truncated + chart_spec/narrative + 溯源 query_spec/sql。
- **FR-16 数据库初始化**：`infra/init.sql` 建 app/data schema、chatbi_ro 只读角色并授权，并建 `app.exemplar_embeddings`（`vector(EMBED_DIM)` + HNSW）；其余 app 表由 SQLAlchemy 迁移/建表；data 表由 `seed/schema.sql` 建。
- **FR-17 数仓表与 seed**：data schema 14 张表（7 张维度：dim_channel / dim_category / dim_product / dim_customer / dim_store / dim_promotion / promotion_store；7 张事实：dwd_exposure_daily / dwd_order / dwd_order_detail / dwd_payment / dwd_refund / dwd_ad_daily / dwd_order_cost）；`python -m seed.seed` 删表重建 + 导入 CSV + 校验行数与 3 个核心指标，幂等，app schema 不清空。
- **FR-18 口径词典（增强包）**：`semantics/metrics.yaml` 为单一来源，`docs/metrics-dict.md` 由其生成；含 GMV/支付订单数/AOV/转化率/退货率/退款率/退款金额占比/新客GMV占比 8 指标；缺失时 S4 标 degraded 不拒答。
- **FR-19 语义缓存写回**：仅 answer 且 rows 非空时由 chat_service 触发 cache_store.put；source 字段标 template/generated。

### 部署
- **FR-20 Docker Compose**：`docker-compose.yml` 含 db(postgres:16)/api(python:3.11-slim+uvicorn)/web(nginx+前端dist)；`.env.example` 含全部变量；`Dockerfile` 构建 api；api 依赖 db 健康后启动。
- **FR-21 Supabase 切换**：生产 DATABASE_URL/DATABASE_RO_URL 指向 Supabase；PGVECTOR_ENABLED=auto 自动探测 vector 扩展；不改代码。
- **FR-22 启动自检**：启动时校验 DATABASE_RO_URL 为只读角色（失败拒绝启动）；探测 pgvector（缺则走 lexical 不阻断）。
- **FR-23 模型与 Mock 开关**：`Settings.use_mock_llm`（默认 `true`）；`main.py` 在导入算法前把 `USE_MOCK_LLM`、`MODEL_SMALL/STRONG/MID`、`EMBED_MODEL`、`EMBED_DIM` 回填 `os.environ`；单测走 Mock，本地联调 `.env` 置 `false`。

## 非功能需求

- **NFR-1 算法不碰库**：`agent/` 不 import 数据库驱动，不持连接串；只通过注入的 runner/cache_store/resources。
- **NFR-2 物理兜底不可绕过**：QueryRunner 9 条检查写死，模板快道/手工重放等旁路调用同样受约束。
- **NFR-3 报表只读快照**：GET /api/reports/{id} 不执行 SQL、不调算法、不走降级。
- **NFR-4 缓存不存数据**：semantic_cache 只存 query_spec/sql/chart_spec，不存 rows/narrative。
- **NFR-5 零资源可用**：L1/模板/示例/别名缺失时服务正常启动、问数链路可走通。
- **NFR-6 pgvector 降级**：pgvector 不可用时 S3 检索自动走 lexical，不报错不阻断启动。
- **NFR-7 可观测**：每次问数落 query_logs（sql/row_count/elapsed_ms/error_code/cached/trace）。

## 约束

- **技术**：Python 3.11、FastAPI、SQLAlchemy 2.0、Pydantic v2、psycopg 3、PostgreSQL 16；不引入其他框架。
- **业务**：不做前端、不做算法内部、不做鉴权、不做流式、不做报表编辑器、不做数据源管理。
- **依赖**：算法 `agent/` 模块已就绪（由 `算法问答链路` Spec 交付）；前端 dist 由前端 Spec 交付（本步 web 容器用占位即可）。

## 假设

- 算法 `agent/` 暴露 `ask(question, session_id, history, runner, cache_store, resources) -> ChainResult` 入口。
- data schema 初始为空时，首次启动后需手动执行 `python -m seed.seed`。
- LLM/Embedding 三元组由 env 配置，本步可用 Mock 或真实 API。
- 前端 dist 本步可先用 nginx 默认页占位，前端 Spec 完成后替换。

## 验收标准

### AC-1：分层与依赖边界
- **Type**: `rule`
- **Given**: 后端代码库
- **When**: 检查模块依赖方向
- **Then**: api→services→agent/query/storage；agent 不 import 数据库驱动；services 是唯一调 agent 的层；storage 不反向依赖
- **Pass Condition**: grep `backend/app/agent` 无 psycopg/sqlalchemy import；api 路由文件不直接 import agent
- **Evidence**: grep 输出 + 依赖图

### AC-2：12 个接口全部注册
- **Type**: `rule`
- **Given**: FastAPI app 启动
- **When**: 访问 OpenAPI schema
- **Then**: 存在 12 条路由（POST /chat/ask、POST /chat/clarify、GET /sessions、GET /sessions/{id}/messages、DELETE /sessions/{id}、DELETE /sessions、POST /reports、GET /reports、GET /reports/{id}、PATCH /reports/{id}、DELETE /reports/{id}、GET /health），统一前缀 /api
- **Pass Condition**: OpenAPI paths 与 SDD §2 接口清单一致
- **Evidence**: `/openapi.json` paths 列表

### AC-3：统一响应包
- **Type**: `rule`
- **Given**: 任意接口调用
- **When**: 收到响应
- **Then**: 响应体为 `{code, message, data, trace_id}`；code=0 时 data 非 null；code≠0 时 data=null
- **Pass Condition**: 所有接口响应符合统一包格式
- **Evidence**: 接口测试响应样例

### AC-4：ChainResult 透传与互斥
- **Type**: `rule`
- **Given**: /chat/ask 返回 assistant 消息
- **When**: 分别触发 answer/clarify/reject
- **Then**: 后端只加 message_id/session_id、剥离 trace；result/clarify/reject 互斥；clarify/reject 状态下 result 非空则 500
- **Pass Condition**: 三种出口形状与算法 §7.4 一致，互斥校验生效
- **Evidence**: 三种出口响应 JSON + 互斥校验测试

### AC-5：QueryRunner 物理兜底 9 条
- **Type**: `rule`
- **Given**: PgQueryRunner.run
- **When**: 传入违规 SQL（写操作/多语句/非 data 表/无 LIMIT/超 max_rows/含 app. 前缀等）
- **Then**: 返回 error_code=SQL_REJECTED，不执行
- **And When**: 合规只读 SELECT
- **Then**: 正常执行返回 QueryResult
- **Pass Condition**: 9 条兜底规则各有对应测试，违规均 SQL_REJECTED
- **Evidence**: QueryRunner 测试用例输出

### AC-6：QueryResult 归一化
- **Type**: `rule`
- **Given**: 执行返回 PG 原始结果
- **When**: 归一化
- **Then**: columns 含 key/title/type（number/string/date）；数值转 float/int；日期 ISO 字符串；null 保留
- **Pass Condition**: 三种类型列各正确映射
- **Evidence**: 归一化测试

### AC-7：失败分流
- **Type**: `rule`
- **Given**: runner 返回不同 error_code
- **When**: 算法链路处理
- **Then**: SQL_REJECTED/SQL_FAILED 首次回炉一次，二次 sql_execute_failed；QUERY_TIMEOUT → reject(timeout) 不重试；空结果 → answer
- **Pass Condition**: 四种场景出口与重试次数正确
- **Evidence**: 失败分流测试

### AC-8：CacheStore 读写
- **Type**: `rule`
- **Given**: PgCacheStore
- **When**: put 后 get
- **Then**: 未过期返回 {query_spec, sql, chart_spec}；过期返回 None；不存 rows/narrative
- **Pass Condition**: get/put 语义与 TTL 正确
- **Evidence**: CacheStore 测试

### AC-9：L0 Introspection
- **Type**: `rule`
- **Given**: data schema 有 14 张表
- **When**: introspector.l0()
- **Then**: 返回 {tables, columns, data_range, schema_version}；含 14 张表及列信息；schema_version 随结构变化
- **Pass Condition**: L0 结构完整且 schema_version 变化触发重读
- **Evidence**: introspection 测试

### AC-10：资源降级
- **Type**: `rule`
- **Given**: metrics.yaml/模板/示例/别名文件不存在
- **When**: 服务启动并问数
- **Then**: 启动成功，问数链路走通，plan.degraded=true，无 reject
- **Pass Condition**: 零增强包下完整问数返回 answer
- **Evidence**: 零资源端到端测试

### AC-11：pgvector 自动降级
- **Type**: `rule`
- **Given**: PGVECTOR_ENABLED=auto 且无 vector 扩展
- **When**: 服务启动 + S3 检索
- **Then**: 启动不报错；检索走 lexical 关键词通道
- **Pass Condition**: 无 pgvector 时服务正常启动且检索可用
- **Evidence**: 无 pgvector 环境的启动日志 + 检索测试

### AC-12：报表只读快照
- **Type**: `rule`
- **Given**: 已存报表
- **When**: GET /api/reports/{id}
- **Then**: 直接读 snapshot_columns/snapshot_rows/chart_spec/narrative/snapshot_truncated 组装 result；不执行 SQL、不调算法
- **Pass Condition**: 打开报表不触发 runner 调用
- **Evidence**: 报表打开测试（runner mock 断言未被调用）

### AC-13：报表存为约束
- **Type**: `rule`
- **Given**: /api/reports
- **When**: message_id 非 answer 或 rows 为空 → 422 MESSAGE_NOT_QUERYABLE；同名且 overwrite=false → 409；chart_type 非 bar/line → 拒绝
- **Then**: 对应 HTTP 状态码与 code
- **Pass Condition**: 三种约束各返回正确错误
- **Evidence**: 报表接口约束测试

### AC-14：存储表结构
- **Type**: `rule`
- **Given**: app schema 建表后
- **When**: 对照 SDD §4 字段表
- **Then**: sessions/messages/reports/semantic_cache/query_logs 五张表字段完全一致；messages 含 query_spec/sql/chart_spec/clarify_state 分列；reports 含 snapshot_* 列
- **Pass Condition**: 表结构与 SDD §4 diff 为零
- **Evidence**: 表结构对照

### AC-15：澄清状态暂存
- **Type**: `rule`
- **Given**: clarify 出口
- **When**: messages.clarify_state 落库
- **Then**: 含 {clarify_id, original_question, missing, options, expires_at}；/chat/clarify 用结构化补全调算法，不拼自然语言；过期/不存在 → 409
- **Pass Condition**: clarify_state 结构与补全逻辑正确
- **Evidence**: 澄清流程测试

### AC-16：消息落库与 trace 剥离
- **Type**: `rule`
- **Given**: 一次问数完成
- **When**: 检查 messages 与 query_logs
- **Then**: user + assistant 两条消息入库；assistant.payload 为 ChainResult（不含 trace）；query_logs 含 sql/row_count/elapsed_ms/error_code/cached/trace
- **Pass Condition**: payload 无 trace 字段，trace 在 query_logs
- **Evidence**: 落库数据断言

### AC-17：语义缓存写回条件
- **Type**: `rule`
- **Given**: 不同出口
- **When**: answer 且 rows 非空 → put；clarify/reject/空结果 → 不 put
- **Then**: put 内容仅 query_spec/sql/chart_spec；source 标 template/generated
- **Pass Condition**: 写回条件与内容正确
- **Evidence**: 缓存写回测试

### AC-18：Docker Compose 可启动
- **Type**: `rule`
- **Given**: .env 已配置
- **When**: docker compose up -d
- **Then**: db/api/web 三容器健康；/api/health 返回 ok；干净环境可完成一次问数
- **Pass Condition**: 三容器 healthy + 一次问数成功
- **Evidence**: compose ps 输出 + 问数 curl 结果

### AC-19：只读角色自检
- **Type**: `rule`
- **Given**: 启动时
- **When**: DATABASE_RO_URL 角色非只读
- **Then**: 启动失败并报错
- **Pass Condition**: 非只读角色时拒绝启动
- **Evidence**: 启动自检测试

### AC-20：数据 seed 幂等
- **Type**: `rule`
- **Given**: data schema
- **When**: 执行 python -m seed.seed 两次
- **Then**: 两次结果行数与 3 个核心指标一致；app schema 不清空
- **Pass Condition**: seed 幂等且不影响 app
- **Evidence**: 两次 seed 结果对比

## 开放问题

- [ ] 前端 dist 本步用 nginx 默认页占位还是等前端 Spec 产出？（建议占位，前端 Spec 完成后替换镜像构建上下文）
- [ ] pgvector 的 exemplar_embeddings 表是否本步建？（建议在 infra/init.sql 或 seed 中建，按 PGVECTOR_ENABLED 条件创建）
