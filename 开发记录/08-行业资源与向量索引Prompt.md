# 08・行业资源与向量索引 Prompt（L0 / L1 / 模板 / 示例 / pgvector）

> 五轮分开做，一轮人审通过后再贴下一轮。
> 轮次依赖：1 → 2 → 3 → 4 → 5；2 与 3 可并行，但 4 必须先有第 3 轮的 `exemplars.yaml`；5 只做资源接线验证，不跑测例问句。
> Embedding 用户会提供，不要写进仓库。第 1~3 轮用不到，不要开口要；第 4 轮建向量表、把示例问句做成向量时再向用户要 `EMBEDDING_BASE_URL` / `EMBEDDING_API_KEY` / `EMBED_MODEL` 以及**维度**。没给之前不要猜、不要用假向量凑。
> 全程硬边界：算法不直连库（`algorithm/` 不 import psycopg / sqlalchemy）；资源文件是配置文件，不是业务数据表；任何增强包缺失，主链路必须照常跑（NFR-5）。

---

## 现状盘点（截至 2026-11-10，已核实）

### 已经做过、本轮不要重做的

| # | 事项 | 落点 |
| :--- | :--- | :--- |
| 1 | Mock L0 已彻底移除：`algorithm/semantic/loader.py` 不存在，`d_order` / `d_order_item` 那套五表 Mock 不在运行路径 | `algorithm/` 目录 |
| 2 | L0 真抽取已接：`PgIntrospector.l0()` 读 `information_schema.columns`（`data` schema），带列注释，返回 `{tables, columns, data_range, schema_version}` | `backend/app/query/introspection.py` |
| 3 | 算法侧 L0 由后端注入：`ResourceProvider.l0()` 直接调 `PgIntrospector`，经 `config["configurable"]["resources"]` 传入 | `backend/app/resources/provider.py`、`algorithm/nodes/_common.py` |
| 4 | 启动强制 L0：lifespan 里 `PgIntrospector().l0()` 失败即抛错，不静默退回 Mock | `backend/app/main.py` |
| 5 | 白名单已同步为真实 14 张表（7 维 + 7 事实） | `introspection.DATA_TABLES`、`sql_guard.ALLOWED_TABLES` |
| 6 | L1 文件已存在：`metrics.yaml`（8 个指标 + 4 个维度） | `backend/semantics/metrics.yaml` |
| 7 | 模板/示例/别名的读取通道已存在，文件缺失时返回空、不报错 | `provider.templates()/exemplars()/aliases()` |
| 8 | 向量检索骨架已存在：扩展探测、`vector_search()`、`lexical_search()` 降级 | `backend/app/resources/retrieval.py` |
| 9 | Supabase 已建 `data` schema 14 表并导入种子数据；只读角色 `chatbi_ro` 读通写拒 | 远端库 |

### 未做 / 已知缺陷（按优先级）

| 级别 | 问题 | 证据 |
| :--- | :--- | :--- |
| **P0** | `_load_l0()` 查 `data.dim_date`，但库里没有这张表（14 表清单无 `dim_date`）→ 后端启动会直接失败 | `introspection.py` 第 92~97 行 |
| **P0** | `l0()` 首次返回 `schema_version=""`（`_schema_version` 在 `_load_l0()` 之后才赋值） | `introspection.py` 第 42~49 行 |
| P1 | L1 结构与消费不匹配，口径实际从未生效：`retrieve.py` 用 `for name, defn in l1.items()`，而 `metrics.yaml` 顶层是 `metrics:` 列表 | `algorithm/nodes/retrieve.py` 第 26~30 行 |
| P1 | 口径取错表 / 列：`GMV = SUM(pay_amount) WHERE order_status='paid'` 挂在 `dwd_order`（该表无 `pay_amount`）；转化率分母写 `dwd_traffic.uv`（库中无此表） | `metrics.yaml` |
| P1 | `doc_type` 语义冲突：`schema.sql` 注释写「refund=退货单 / return=退款单」，`metrics.yaml` 却是 `return` 算退货率、`refund` 算退款率 | 两处对不上，必须查库确认 |
| P1 | 模板字段三方不一致：`template.py` 读 `required_slots/metric_columns/sql_template`；`bootstrap.py` 写 `sql_pattern`；SDD §4.5 写 `signature/sql` | 未统一 |
| P1 | 示例库为空；且 `retrieve.py` 把示例全量塞进 `plan.few_shot`，没有相似度筛选 | `retrieve.py` 第 37~38 行 |
| P2 | pgvector 探测打在 `public.exemplar_embeddings`，与「app 侧资源」定位不符；后端没有 embedding 客户端 | `retrieval.py` |
| P2 | `backend/.env` 未落盘（只有 `.env.example`），实跑前需补齐连接信息 | 已确认目录 |

---

## 第 1 轮・补齐 L0 抽取，修掉启动硬伤

```text
本轮只修 L0 抽取。不要改 L1 YAML、不要写模板/示例、不要建 pgvector、不要改 data schema 的业务表和种子数据、不要动前端。

先读：
- docs/SDD-算法应用.md 第 4.2、2.5、9.4 节
- docs/SDD-后端.md 第 3.6、5.1 节
- backend/app/query/introspection.py
- backend/app/resources/provider.py
- backend/app/main.py
- backend/app/query/sql_guard.py
- backend/seed/schema.sql（14 张表的 DDL 与中文 COMMENT）

现状（已做过，不要重做）：
- Mock L0 已移除，algorithm 里没有 semantic/loader.py，D 盘那套 d_order 五表 Mock 不在运行路径；
- L0 已由 PgIntrospector 从 information_schema 真抽取，经 ResourceProvider 注入算法；
- 启动时强制 warmup，失败即启动失败；
- 14 张表白名单已在 introspection 与 sql_guard 同步。

必须修的问题：
1. 【P0】_load_l0() 里 data_range 查的是 data.dim_date，这张表不存在，后端起不来。
   改成从事实表取边界：MIN/MAX(dwd_payment.pay_date)、MIN/MAX(dwd_order.order_date)、MIN/MAX(dwd_refund.refund_date)，
   聚合出整体 min_date / max_date。不要新建 dim_date，不要改业务库。
2. 【P0】l0() 首次调用返回的 schema_version 是空串（赋值顺序问题）。保证返回体里的 schema_version 与本次快照一致。
3. 补齐 SDD §4.2 要求、当前缺失的 L0 内容：
   - 每列：nullable、是否主键、外键指向（table.column）；
   - 低基数列采样：distinct 数 ≤ 50 的列，取全部 distinct 值（按值排序）；> 50 只取 distinct 计数，不取全量值；
   - 数值列：min / max；
   - 表级行数：用 pg_class.reltuples 近似（允许误差），禁止 COUNT(*) 全表扫。
4. 采样 SQL 必须走只读连接，且每条带 LIMIT；单表采样失败只跳过该列并记 warning，不能让整次 L0 失败（除非 information_schema 都读不到）。
5. 输出结构定死，不要改字段名（算法侧已按此消费）：
   {
     "tables": [{"name", "comment", "row_count_est", "columns": [{"name","type","comment","nullable","is_pk","fk","distinct_count","enum_values","min","max"}]}],
     "columns": [{"table","name","type","comment"}],
     "data_range": {"min_date","max_date"},
     "schema_version": "16位哈希"
   }
   注意：columns 平铺数组保留（S3 用它做关键词匹配），新增信息放 tables[].columns。
6. 缓存与失效：保留进程内缓存；schema_version 变化（表/列/类型哈希变化）时重读。schema_version 只包含表名+列名+类型，不包含注释与数据，避免每次改注释就重读。
7. 连接配置：读 DATABASE_META_URL，缺省回落 DATABASE_RO_URL。仓库里没有 backend/.env，实跑前向我要连接串（沿用 07 轮那套 Supabase Session Pooler，不要重新要、不要换 5432 直连），拿到后写进本地 .env，不要提交。
8. 不改 data schema，不改 algorithm 里任何文件（除必要的类型注释）；algorithm 必须仍然零 DB import。

不要做：
- 不要把 L0 快照写进 app schema 或 public；
- 不要让 algorithm 自己去读库；
- 不要为采样跑全表 COUNT / 无 LIMIT 的 SELECT DISTINCT；
- 不要把注释当列名回退（当前注释缺省回落列名，可以保留，但要在交付里标出哪些列没读到 COMMENT）。

交付（等人确认后再进入第 2 轮）：
- introspection.py 的改动说明（改了哪几段、为什么）；
- 一份真实 L0 快照摘要：14 张表各自列数、COMMENT 读取率（有注释的列 / 总列数）、data_range 实际值、schema_version；
- 枚举采样样例：dim_channel、dim_promotion.promotion_type、dwd_order.order_status、dwd_payment.pay_status、dwd_refund.doc_type 各取到的实际值；
- 一份对照：d_order / d_order_item / dwd_traffic 这三个历史名字在仓库里是否已彻底消失（给出 grep 结果）；
- 启动自检结论：L0 能否通过；失败时报错是否明确（不是静默空结构）。
```

人审：`dim_date` 硬依赖是否真的去掉了；采样有没有全表扫；`doc_type` 实际值长什么样（第 2 轮要用）；`algorithm/` 是否仍然零 DB import；失败会不会又退回空 L0 假装成功。

---

## 第 2 轮・按 L0 冷启动 L1 口径字典（YAML，人审之后才算数）

```text
本轮只做口径词典：把 backend/semantics/metrics.yaml 写对、写好，并让 S3/S4 真正消费它。
不要写模板库、不要写示例库、不要建 pgvector、不要改 data schema 业务表。

先读：
- docs/SDD-算法应用.md 第 4.3、4.7、4.8、2.6 节
- docs/SDD-后端.md 第 5.3 节
- backend/semantics/metrics.yaml（现稿）
- backend/semantics/bootstrap.py
- algorithm/nodes/retrieve.py、algorithm/nodes/plan.py
- backend/app/resources/provider.py
- backend/seed/schema.sql、backend/seed/seed.py（里面有行数与核心指标期望值）
- 第 1 轮交付的 L0 快照（枚举实际值、data_range）

现状（已做过，不要重做）：
- metrics.yaml 已存在，含 8 个指标与 4 个维度，provider.l1() 能读到；
- 缺字典时链路不报错（降级通道已在）。

必须修的问题：
1. 结构不匹配：retrieve.py 用 for name, defn in l1.items() 遍历，而 YAML 顶层是 metrics: 列表 → 口径从未进入 S3/S4。
   统一为下面的定稿结构，并且把 retrieve.py / plan.py 改成按这个结构取数。
2. 口径写错表/列：
   - GMV 现在写 SUM(pay_amount) WHERE order_status='paid' 且挂 dwd_order —— dwd_order 没有 pay_amount，只有 total_amount；
     正确口径是 dwd_payment.pay_amount WHERE pay_status='success'（按 pay_date 归期）。
   - 转化率分母现在写 dwd_traffic.uv —— 库里没有 dwd_traffic，实际分母是 dwd_exposure_daily.uv（下单转化分母可用 exposure_count/session_count）。
   - 退货率 / 退款率的 doc_type 必须先 SELECT DISTINCT doc_type FROM data.dwd_refund 看实际值，
     以库里的值为准（schema 注释与现稿 YAML 互相矛盾），确认后在 YAML 里写死并注明依据。
3. 派生指标必须写成可展开的引用（引用其他 metric.key），不要让模型自由发挥：
   支付订单数 = COUNT(DISTINCT dwd_payment.order_id) WHERE pay_status='success'；
   AOV = gmv / paid_orders；转化率 = paid_orders / uv。
4. 多口径必须显式登记，交给 S4 决定是否澄清：
   退货率（按单数 / 按金额）、转化率（下单转化 / 支付转化）都要有 ambiguity 候选，不许只留一个默认值还假装唯一。
5. 大促日历不许写死字面日期（不要出现「2026-06-16」这种硬编码当口径来源）：
   大促/预热/日常的定义来自 dim_promotion（promotion_type、start_date、end_date），
   YAML 里写「怎么从 dim_promotion 取某年某类档期」的规则 + 当前库采样到的档期清单（只作展示，标注 sampled_at）。

YAML 定稿结构（字段名写死，不要自创）：
version: "l1-2026.11"
updated_at: "2026-11-10"
owner: "运营"
metrics:
  - key: gmv
    name: GMV
    aliases: [成交额, 销售额, 销售额GMV]
    definition: 支付成功金额，不含取消与退款
    formula: "SUM(dwd_payment.pay_amount)"
    tables: [dwd_payment]
    filters: ["pay_status = 'success'"]
    grain: pay_date
    derived: false
    ambiguity: []
    verified: true
    verified_sql: "SELECT SUM(pay_amount) FROM data.dwd_payment WHERE pay_status='success' AND pay_date BETWEEN :start AND :end"
dimensions:
  - key: channel
    name: 渠道
    column: dwd_payment.channel_code
    lookup_table: dim_channel
    lookup_key: channel_code
    lookup_label: channel_name
    aliases: [渠道, 来源]
calendar:
  promotion:
    table: dim_promotion
    type_column: promotion_type
    start_column: start_date
    end_column: end_date
    types: [大促, 预热, 日常]
    sampled_periods:
      - {name: "618大促", type: "大促", start: "2026-06-16", end: "2026-06-18", sampled_at: "2026-11-10"}
  relative:
    - {key: last_week, rule: "本期结束日往前推 7 天"}
    - {key: yoy, rule: "去年同期，按日对齐"}
unresolved: []   # 跑不通 / 库里对不上的，列在这里，不要编

执行要求：
1. 先验算再落盘：每个 metric 都写一条校验 SQL，在 data schema 实跑，结果必须与 seed.py 的期望值或 07 轮验算清单一致。
   跑不通或对不上 → 不写进正式 YAML，记入 unresolved，并把 SQL 与报错贴出来。
2. 消费侧改造：
   - provider.l1() 原样返回该结构（不要在这里做业务判断）；
   - retrieve.py：按问题文本与 aliases 命中 metric / dimension，产出 evidence.metrics 为 [{key,name,formula,ambiguity}]，evidence.entities 来自 aliases；
   - plan.py：只把命中的口径候选塞进 prompt（不是整本字典），并保留 degraded 标记；
   - 字典缺失 / 为空 / 解析失败：degraded=true，链路照常走，不抛异常。
3. 同步 docs/metrics-dict.md（由 YAML 生成的表：指标 / 一句话口径 / 公式 / 同义词 / 数据来源表），避免两份漂移；不要手改 md 再回改 yaml。
4. 不改 algorithm 之外的运行逻辑；不新增管理接口（SDD §4.8：本版入口只有 python -m semantics.bootstrap）。

交付（等人确认后再进入第 3 轮）：
- metrics.yaml 定稿全文；
- 校验对照表：指标 / 校验 SQL / 实跑结果 / 是否与 seed 期望值一致（至少覆盖 GMV、支付订单数、AOV、转化率、退货率、退款率、退款金额占比、新客 GMV 占比）；
- doc_type 实际取值截图或查询结果，以及最终选择哪个值代表退货；
- retrieve.py / plan.py / provider.py 的改动说明（前后行为差异）；
- C 档回归：临时把 metrics.yaml 改名 → 仍能完整出表，且 degraded=true 出现在 trace / plan 里。
```

人审：口径是不是用对了表列（GMV 在 `dwd_payment`）；`doc_type` 到底哪个值代表退货；大促期是不是来自 `dim_promotion` 而不是手写日期；多口径有没有登记；算法有没有仍然不读库；没有字典时会不会红。

---

## 第 3 轮・模板库 + 示例库（YAML，SQL 只作 Few-shot）

```text
本轮只做 backend/semantics/ 下的模板库、示例库、别名文件，以及对应的读取与检索改造。
不要建 pgvector、不要调 embedding、不要改 data schema 业务表、不要新增接口。

先读：
- docs/SDD-算法应用.md 第 4.4、4.5、4.6、4.7、4.8 节
- algorithm/nodes/template.py（它实际读 required_slots / metric_columns / sql_template）
- algorithm/nodes/gen_sql.py（few_shot 如何进 prompt）
- algorithm/nodes/retrieve.py
- backend/app/resources/provider.py
- backend/semantics/bootstrap.py
- 第 2 轮定稿的 metrics.yaml

现状（已做过，不要重做）：
- provider 已经有 templates() / exemplars() / aliases() 三个通道，文件缺失返回空、不报错；
- 空模板库时 S2 直接未命中，主链路不受影响。

必须修的问题：
1. 文件格式统一为 YAML（与 L1 一致）：templates.yaml、exemplars.yaml、aliases.yaml。
   provider 改成读 YAML；删除 templates.json / exemplars.json 的读取与生成逻辑（不保留双份）。
2. 字段三方不一致：template.py 读 required_slots / metric_columns / sql_template；bootstrap.py 写 sql_pattern；SDD §4.5 写 signature / sql。
   以 template.py 为准统一为 required_slots / metric_columns / sql_template，并同步修正 SDD §4.5 的示例（只改文档示例，别改协议）。
3. bootstrap.py 现在会直接覆盖正式文件。改成只产出草稿：templates.draft.yaml / exemplars.draft.yaml / aliases.draft.yaml，
   并在文件头写 generated_at、source=schema、reviewed=false。正式文件只能人审后手动转正（SDD §4.8 铁律）。
4. retrieve.py 把示例全量塞进 few_shot。改为按 tags + 问题关键词（或与 metric/dimension key 的交集）筛 top_k，默认 k=3；筛不到就空列表。

模板库定稿结构（字段名写死）：
version: "tpl-2026.11"
templates:
  - id: tpl_metric_single_period
    name: 单指标单期聚合
    required_slots: [metrics, time_range]
    metric_columns:
      GMV: dwd_payment.pay_amount
      支付订单数: dwd_payment.order_id
    sql_template: |
      SELECT SUM({metric_col}) AS v
      FROM dwd_payment
      WHERE pay_status = 'success'
        AND pay_date BETWEEN '{start_date}' AND '{end_date}'
    verified: true
    notes: 仅覆盖单指标、无维度、无对比；有维度或对比时不要命中

示例库定稿结构（字段名写死）：
version: "ex-2026.11"
exemplars:
  - id: ex_yoy_gmv
    question: 今年618大促 GMV 同比去年是多少
    sql: |
      WITH cur AS (
        SELECT SUM(pay_amount) AS v FROM dwd_payment
        WHERE pay_status='success' AND pay_date BETWEEN '2026-06-16' AND '2026-06-18'
      ), prev AS (
        SELECT SUM(pay_amount) AS v FROM dwd_payment
        WHERE pay_status='success' AND pay_date BETWEEN '2025-06-16' AND '2025-06-18'
      )
      SELECT cur.v AS cur_v, prev.v AS prev_v, (cur.v - prev.v) / NULLIF(prev.v, 0) AS yoy
      FROM cur, prev
    query_spec: {metrics: [gmv], time_range: {start: "2026-06-16", end: "2026-06-18"}, comparison: {type: yoy}}
    tags: [同比, 大促, 时间窗]
    difficulty: medium
    source: manual
    verified: true

内容要求：
1. 模板 4~6 条，至少覆盖：单指标单期、单指标分维度、分维度 TopN、同比 / 环比两期对比；
   模板里出现表名与列名必须真实存在于 data schema，且与 L1 口径一致。
2. 示例 10~20 条，至少覆盖：同比、环比、TopN、除零保护（NULLIF）、日期边界（含首日/末日）、大促期窗口、下单转化率、支付转化率、AOV（派生）、退货率（多口径其一）。
3. 每条示例 SQL 必须实际在 data schema 跑通；跑不通的不许进正式文件，放草稿并注明原因。
4. 示例只用于 few-shot 喂 Coder，不参与答案比对、不做结果校验、不写进缓存当作答案。
5. aliases.yaml 保留实体/维度别名（如 江浙沪 → 浙江/江苏/上海；渠道别名），未命中走澄清，不拒答。
6. 所有文件带 version；version 变化要让 S2 缓存语义上失效（沿用现有 cache_key + template_version 机制，不要新增表）。

不要做：
- 不要把模板 SQL 当唯一路径（未命中必须继续 S3）；
- 不要用示例库做结果对错判定；
- 不要新增模板管理接口或前端页面；
- 不要让 bootstrap 直接写正式文件。

交付（等人确认后再进入第 4 轮）：
- templates.yaml / exemplars.yaml / aliases.yaml 全文；
- 每条模板与示例的实际执行记录（SQL、返回行数、是否报错）；
- provider / retrieve / bootstrap 的改动说明；
- 对照表：模板命中条件（槽位齐全 / 能落列 / 口径无歧义）逐条怎么判；
- A 档 vs C 档对比：有模板/示例 vs 临时移走三个 YAML，链路都能出表。
```

人审：模板字段是否与 `template.py` 一致；每条示例 SQL 是不是真能跑；有没有把示例当答案比对；正式文件会不会被脚本覆盖；未命中是否一定回落到 S3。

---

## 第 4 轮・同一个 Supabase 上建 pgvector，只索引示例问句

```text
本轮只做示例问句的向量索引与检索接入。前置条件：用户已给 EMBEDDING_BASE_URL / EMBEDDING_API_KEY / EMBED_MODEL / 维度。
没给就停在这里，不要猜维度、不要用假向量、不要用哈希冒充 embedding。

先读：
- docs/SDD-算法应用.md 第 4.6、4.7、9.4 节
- backend/app/resources/retrieval.py
- backend/app/resources/provider.py
- backend/app/core/config.py（已有 embedding_base_url / embedding_api_key / embedding_model）
- backend/semantics/exemplars.yaml（第 3 轮产出）
- backend/.env.example

现状（已做过，不要重做）：
- 已有 detect_pgvector() / vector_search() / lexical_search() 三个函数；
- 当前探测 public.exemplar_embeddings，该表不存在，实际一直走 lexical；
- 后端没有 embedding 客户端。

要做的：
1. 建向量表（同一个 Supabase 实例，app schema，不动 data schema）：
   CREATE EXTENSION IF NOT EXISTS vector;
   CREATE TABLE IF NOT EXISTS app.exemplar_embeddings (
     id BIGSERIAL PRIMARY KEY,
     exemplar_id TEXT NOT NULL,
     question TEXT NOT NULL,
     embedding vector(<用户给的维度>) NOT NULL,
     model TEXT NOT NULL,
     dim INT NOT NULL,
     content_hash TEXT NOT NULL,
     updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
     UNIQUE (exemplar_id, model)
   );
   索引：CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)；
   若该实例不支持 hnsw 则用 ivfflat (lists 取 100 以内的小值)，并把实际选型写进交付。
   维度冲突处理：若表已存在且维度与本次不一致，立刻停下报告，不要 DROP、不要自动改维度。
   CREATE EXTENSION 失败（权限不足）：记录后跳过，主链路继续走 lexical，不阻断启动。

2. 写入脚本 backend/semantics/embed_exemplars.py（入口 python -m semantics.embed_exemplars）：
   - 源数据只来自 exemplars.yaml 的 question 字段（只索引问句，不索引 SQL、不索引文档正文）；
   - 幂等：按 (exemplar_id, model) 做 upsert；content_hash = sha256(question)，未变化则跳过；
   - 批量请求（每批 ≤ 32 条），单批失败重试 1 次，仍失败则记入失败列表继续下一批；
   - 结束后打印：总数 / 跳过 / 成功 / 失败及原因；
   - 使用 backend 的 EMBEDDING_* 配置，不读 algorithm 的配置。

3. 检索改造（backend/app/resources/retrieval.py）：
   - detect_pgvector() 改为探测 app.exemplar_embeddings 与 vector 扩展，不再看 public；
   - vector_search(question) 内部负责先取 query embedding，再查：
     SELECT exemplar_id, question, 1 - (embedding <=> %s::vector) AS score
     FROM app.exemplar_embeddings
     WHERE model = %s
     ORDER BY embedding <=> %s::vector
     LIMIT %s;
   - 连接用 DATABASE_URL（app schema 不开放给 chatbi_ro），只读查询；
   - 任何异常（无 key、超时、维度不符、表不存在）→ 返回空并记 warning，由 provider 降级 lexical，不抛错、不让 S3 失败。

4. provider.exemplars() 改为：
   - 有向量通道：按当前问题取 top_k（默认 5），映射回 exemplars.yaml 的完整对象（question + sql + tags）；
   - 无向量通道：lexical_search 降级；
   - 两者都空：返回空列表，S3 继续，不报错。
   注意：向量只负责"召回哪几条"，SQL 仍来自 YAML 正式文件，不允许把向量表里的内容当 SQL 来源。

5. 补 backend/.env.example：EMBEDDING_BASE_URL / EMBEDDING_API_KEY / EMBEDDING_MODEL / EMBED_DIM，注明维度必须与建表一致；真实 key 只进本地 .env。

6. 不新增管理接口（SDD §4.8）；不做前端向量管理页；不索引文档、不索引业务表、不建 data schema 的向量列。

不要做：
- 不要在 data schema 或业务表上加 embedding 列；
- 不要把向量检索失败变成拒答；
- 不要用假向量 / 随机向量 / 哈希向量做联调；
- 不要在维度不一致时自动 DROP TABLE 重建。

交付（本轮收尾即整个 08 完成）：
- 建表 DDL 与实际执行结果（扩展版本、索引类型）；
- embed_exemplars.py 与一次完整摄取记录（条数、耗时、失败列表）；
- retrieval.py / provider.py 改动 diff 说明；
- 检索验证：给 10 条问句，列出 top3 召回结果与人工判定是否相关；
- 降级验证：清空 app.exemplar_embeddings 或断网后，同一问题仍能出表（走 lexical）；
- 口径一致性检查：向量召回出的示例，其 SQL 与 L1 口径不冲突。
```

人审：维度是不是用户给的、没有猜；只索引了问句；索引建在 `app` 而不是 `data`；检索失败会不会变红；SQL 来源是否仍然只有 YAML。

---

## 第 5 轮・只验证资源有没有接上（不跑测例问句）

```text
本轮只做一件事：证明四类资源真的接进了运行路径。禁止跑 C01~C19 或任何业务问句，禁止调用 LLM，禁止造数、改口径、改模板。
允许启动后端做 lifespan 自检（L0 是硬依赖，必须真启动一次），但不发 /api/chat/ask 请求；LLM key 不配也必须能启动。

先读：
- 第 1~4 轮各自的交付记录
- backend/app/resources/provider.py、backend/app/resources/retrieval.py
- backend/app/main.py（lifespan）
- algorithm/nodes/retrieve.py、algorithm/nodes/plan.py、algorithm/nodes/template.py
- backend/semantics/ 下的 metrics.yaml / templates.yaml / exemplars.yaml / aliases.yaml

验证项与判定标准（逐条给「实际值」，不许写"应该没问题"）：

A. L0
1. 后端能启动，lifespan 里 L0 warmup 通过；把日志里的 schema_version 抄下来。
2. resources.l0() 返回 14 张表；columns 平铺数组非空；data_range 的 min_date / max_date 不是 None。
3. 注释覆盖率：有 COMMENT 的列 / 总列数 ≥ 90%；未读到的列名列清单。
4. 枚举采样抽查：dim_channel、dim_promotion.promotion_type、dwd_order.order_status、dwd_payment.pay_status、dwd_refund.doc_type，各贴出实际取到的值。
5. 反例：把 DATABASE_META_URL 指向一个错误库，确认启动是明确报错（L0LoadError），不是空结构假装成功；验证完改回去。

B. L1 口径
6. resources.l1() 返回顶层含 version / metrics / dimensions / calendar；metrics 条数与 YAML 一致（应为 8），逐条打印 key。
7. 结构对齐：直接在 Python 里模拟 retrieve 的取数逻辑（不调 LLM），确认能按 metrics 列表拿到 key/formula，而不是把 dict 当键值对遍历。
8. plan.py 的 prompt 组装用假 l1 + 假 evidence 走一遍（不调 LLM，只打印最终 user_content），确认塞进去的是"命中的口径候选"，不是整本字典。
9. 降级：临时把 metrics.yaml 改名 → resources.l1() 返回空 dict、不抛异常；恢复文件。

C. 模板 / 示例 / 别名
10. resources.templates() / exemplars() / aliases() 返回条数，与三个文件里的条目数一致。
11. 字段形状对齐：逐条断言模板含 required_slots / metric_columns / sql_template（template.py 真正读的字段），示例含 question / sql / tags。缺字段的条目列出来。
12. 模板 SQL 静态检查（不执行）：出现 {metric_col} / {start_date} / {end_date} 占位符；表名在 L0 的 14 张表内。
13. 示例 SQL 静态检查（不执行）：只读单条 SELECT / WITH；表名在 L0 白名单内；不出现 INSERT / UPDATE / DELETE。
14. 降级：三个文件分别改名 → 对应方法返回空列表 / 空 dict，S3 不抛异常。

D. 向量
15. detect_pgvector() 返回 True；app.exemplar_embeddings 行数 = exemplars.yaml 条数；模型名与维度与 .env 一致（贴出来）。
16. 用一条**示例问句原文**做检索（不是业务问句），top1 应命中它自己；贴出 top3 的 exemplar_id 与 score。
17. 降级：清空 EMBEDDING_API_KEY 重启进程 → detect 为 True 但 vector_search 返回空并记 warning，provider 回落 lexical；验证完恢复 key。

E. 边界
18. algorithm/ 下 grep psycopg / sqlalchemy / postgresql:// 结果为 0。
19. resources 的四个方法（l0/l1/templates/exemplars）在空资源下都不抛异常。
20. 本轮没有新增接口、没有新增 app 表（除第 4 轮的 app.exemplar_embeddings）、没有改 data schema。

不要做：
- 不跑任何业务问句、不跑测例、不调 LLM（除第 16 条用的是示例问句原文，且只走 embedding，不走 chat）；
- 不顺手改代码：发现问题只记录，列成待修清单交给人决定；
- 不启动前端；
- 不用假向量、不临时插数据凑数。

交付：
- 一张验证表：编号 / 验证项 / 实际结果 / 通过与否（20 条全列，必须有实际值）；
- 后端启动日志中与资源相关的几行原文（L0 schema_version、pgvector enabled、各资源加载条数）；
- 待修清单（如果有），按 P0/P1/P2 标注，注明文件与行号；
- 一句话结论：四类资源是否已接上；哪一类只是"文件存在但运行期没生效"。
```

人审：20 条是不是都有实际值；有没有偷偷跑业务问句；L1 那条是不是真的验证了"消费侧能按列表取到"，而不是只看文件存在；降级三条（B9/C14/D17）是否真做了；有没有顺手改代码。

---

## 收尾・五轮做完后的统一验收

| 档位 | 条件 | 必须成立 |
| :--- | :--- | :--- |
| A 档（资源齐全） | L0 + L1 + 模板 + 示例 + 向量全在 | 演示问句答得准；模板快道能命中；示例能召回 |
| C 档（零增强） | 临时移走 `metrics.yaml` / `templates.yaml` / `exemplars.yaml` / `aliases.yaml`，清空 `app.exemplar_embeddings` | S1~S8 完整走通、能出表出图、该澄清的澄清、不该拒的不拒 |

五轮共同的禁止事项：

1. 算法直连库（`algorithm/` 出现 psycopg / sqlalchemy / 连接串）；
2. 把增强包写进 `data` schema 或业务表；
3. 没有资源就报错、拒答、或者偷偷退回 Mock；
4. 硬编码日期当口径来源、硬编码列名当 L0；
5. 把示例 SQL 当答案比对或写进语义缓存冒充结果。

每轮开工先改文档、再写代码。顺序固定：算法 SDD → 后端 SDD → 前端 SDD → PRD → Spec（见 AGENTS.md）。下表是每一轮各自的文档落点，先改完对应行，再动代码：

| 轮次 | 文档 | 改什么 |
| :--- | :--- | :--- |
| 1 | `docs/SDD-后端.md` §3.6 | `data_range` 来源从 `dim_date` 改为事实表边界；补 nullable / PK / FK / 采样 / 行数 |
| 2 | `docs/SDD-后端.md` §5.3、`docs/metrics-dict.md` | 口径公式改为 `dwd_payment` 版；补 `calendar` 与多口径登记 |
| 3 | `docs/SDD-算法应用.md` §4.5 | 模板字段统一为 `required_slots / metric_columns / sql_template` |
| 4 | `docs/SDD-算法应用.md` §4.6、§9.4；`docs/SDD-后端.md` §4.6、§5.1、§6 | 示例检索改为 app 侧向量表 + lexical 降级；provider `exemplars(question)` 与 `aliases()`；后端补 `app.exemplar_embeddings` 表与摄取入口 |
