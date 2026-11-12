# 07・行业库接入 Prompt（电商演示数据 → Supabase）
>四轮分开做，一轮确认后再贴下一轮。密钥向用户要，不要写进仓库。不改平台代码、不打镜像、不起 Compose。

---

## 第 1 轮・只设计库表，先别造数、先别连库

```text
下面只做电商演示库的表结构设计，不要生成 INSERT、不要连 Supabase、不要改问数链路代码。

先读：
- docs/测例.md（全部 C01~C19，逐条看「必查」与「过/不过」）
- docs/metrics-dict.md（若不存在则按测例里的口径描述）
- docs/SDD-后端.md 第 3、4、5 节
- docs/SDD-算法应用.md 第 11.2

仓库里已有 backend/seed/（schema.sql + seed.py + data/*.csv）：那是五表（dwd_order / dwd_traffic / dwd_refund / dim_customer / dim_date）、约 200 单的玩具库，缺 COMMENT、缺门店/活动、也算不出真转化。本轮按测例 C01~C19 重做 DDL，覆盖这批文件，不要在旧五表上修修补补，也不要去改 algorithm 里任何硬编码 L0。

约束：
1. 这是通用 ChatBI，电商大促复盘只是拿来验收的场景。表放在 PostgreSQL 的 data schema，不要放进 app schema（app 是会话/报表），不要写到 public。
2. 最低业务表：客户、类目、商品、订单主表、订单明细、门店、活动档期（含满减与参与门店）。另外必须有转化分母表（按日 × 渠道的访问 / 会话，或等价粒度）。不够可以再加（渠道维、退货事实等）。不要做成生产级电商中台：禁止仓配、SKU 实时库存、结算对账、会员积分、完整 OMS。
3. 转化率：下单转化、支付转化必须是两套「分子 / 分母」，分母来自访问 / 会话，不是「已支付订单 / 全部订单」（那是支付成功率）。对照表里面写清两种口径各自用哪张表、哪几列（对应 C03、C17、C19）。
4. 必须能支撑测例事实：GMV、两种转化、退货率、退货金额、AOV、渠道、类目、满减活动门店。时间窗必须都能从日期列切出来，不要只靠一个 is_promo 布尔：

- 今年大促期间 = 2026-06-16～2026-06-18；去年同窗 = 2025-06-16～2025-06-18（C01 同比）
- 大促首日 = 当年 6/16（C07 按天趋势需覆盖首日，峰值日要能被识别）
- 预热期 = 当年 6/01～6/15（必须单独成窗，禁止用「大促前一周」顶替）
- 大促前一周 = 当年 6/09～6/15；大促后一周 = 当年 6/19～6/25（C04 AOV 对比、C06 日均对比）
- 数据起始日期 ≥ 2025-06-01，使 C13 问「2024 年 618」时超范围拒答
- 全区间连续有日数据，支撑 C16 上周 / 前一周环比（等长相邻两周）

5. 不要建 SKU 级实时库存 / 库存周转表。测例 C01~C19 中无库存类问题，不要为此造表。
6. 每张表、每列写中文 COMMENT。低基数枚举列（渠道、订单状态、支付状态等）值要稳定、可采样。主键、外键、建议索引（时间、渠道、类目、门店）。这是给 L0 自动抽库结构用的。

交付（等人确认后再进入第 2 轮）：

- 一份 ER 说明（表职责 + 关系，中文）
- 完整 DDL（CREATE SCHEMA data + CREATE TABLE + COMMENT），覆盖写入 backend/seed/schema.sql，不要执行
- 一张对照表：C01~C19 各自主要查哪几张表、靠哪些字段验算。重点标注：
  - C03 / C17：两种转化（下单转化、支付转化）的分子分母各用哪张表哪几列
  - C11 / C18：无对应业务表，走拒答（竞品数据、写操作）
  - 活动与门店怎么挂（支撑满减活动的门店维度）
  - 预热期、首日、大促前一周、大促后一周、环比窗各自怎么从日期列切出
  - C09 / C10 / C12 / C19：不查数，走澄清或拒答，无表依赖

```
人审：转化分母、活动 - 门店、预热 / 首日这三块缺了不算「表通过该款」；该砍的是仓配 / 库存 / 结算。C03（两种转化）、C11/C18（拒答无表）、时间窗切换有没有设计歪；有没有误写入 app /public 或实时库存；有没有还在沿用旧五表。

---

## 第 2 轮・按已定表结构准备种子数据，仍不连库

```text
本轮只造数据，不连 Supabase、不执行任何 SQL、不改平台代码。数据要能支撑 docs/测例.md 全部 C01~C19 的事实验算。

先读：
- 第 1 轮交付的 DDL（表结构 + 中文 COMMENT + 对照表）
- docs/测例.md 逐条说明
- docs/metrics-dict.md（指标口径，若不存在则按测例里的口径描述）

约束：
1. 数据量：订单主表 5000~15000 单，覆盖 2025-06-01 ~ 2026-06-25（够做同比、环比、预热、首日、前一周、后一周）。订单明细按 1 单 1~3 行。其余表按关联度生成（客户、商品、门店、活动、流量）。体量不能压到几千以下，否则「渠道 × 类目 × 日」的交叉单元格会大量为空，C02/C05/C07 排不出有意义的序。
2. 时间窗必须自然分布，不要把所有订单塞进大促三天：
   - 2026-06-01~06-15 预热期：有一定订单量，低于大促期
   - 2026-06-16~06-18 大促期：订单峰值，三天每天都有数且峰值日可识别（C07 趋势），含首日 6/16
   - 2026-06-19~06-25 大促后一周：回落
   - 2025-06-16~06-18 去年同期：用于同比，数值要与今年有明显差异（涨或跌均可，但要能算出增长率，C01）
   - 其余日期（2025-06-01~06-15、2025-06-19~06-25、2025 下半年、2026 上半年非大促段）也要有数据，不能断档，保证 C16 任意相邻两周都有数可环比
   - 数据起始日期钉死为 2025-06-01，C13 问「2024 年 618」时应超范围拒答
3. 渠道：至少 4 个渠道（如 app / 小程序 / web / 线下门店），大促期分渠道 GMV 要排出明确高低、不要并列第一（C02）。各渠道转化率要有差异，至少一个渠道明显低于其他渠道，用于 C03「掉得最多」。
4. 类目：至少 6 个类目（如 服饰 / 数码 / 食品 / 家居 / 美妆 / 母婴），保证 C05 退货率 Top5 不缺项。至少 2 个类目退货率超过 8%，且各类目退货率有差异可排序。
5. 转化率分母：流量表按「日 × 渠道」粒度，每天每个渠道有 UV（访客数）和 PV。大促期 UV 高于预热期。下单转化率 = 下单用户数 / UV；支付转化率 = 支付用户数 / UV。两套口径的分子必须能从订单表状态字段切出（下单状态 vs 支付状态）。UV 必须 > 对应渠道的下单/支付用户数，否则转化率 > 100% 不合理。
6. 退货与退款：退货事实表要有 doc_type 区分退货(refund)和退款(return)，且必须有退款金额字段。退货率 = 退货单数 / 支付订单数（C05）；退款金额占比 = 退款金额 / GMV（C15）。按退款发生时间归期，不是按下单时间。
7. 新老客：客户表有 first_pay_date，订单表关联 customer_id。新客 = 首次支付成功落在当前时间窗内的客户。C08 新老客 GMV 占比要能算出来且合计 100%，两者都不为 0。
8. AOV：AOV = GMV ÷ 支付订单数。大促期与大促前一周的 AOV 要有可识别的高低差异（C04），不要两期恰好相等。
9. 活动：活动表存档期（start_date, end_date）、满减门槛、参与门店列表。订单通过门店关联到活动。大促档期 = 2026-06-16~06-18，预热档期 = 2026-06-01~06-15。
10. 枚举值稳定：渠道、订单状态（created/paid/cancelled/refunded）、支付状态（unpaid/paid/refunded）、类目。这些值要在多表间一致，给 L0 采样用。
11. 不要造库存、仓配、结算、积分表的数据。

交付（等人确认后再进入第 3 轮）：

- 每个表一个 CSV，放在 backend/seed/data/，文件名 = 表名.csv，首行是列名，编码 UTF-8。
- 一份数据设计说明：每个表的行数、关键分布（订单量按天趋势、渠道占比、类目占比、大促期 vs 平日倍数）、故意做的异常点（如某渠道转化率明显下跌用于 C03、某类目退货率超 8% 用于 C05、大促期 vs 前一周 AOV 差异用于 C04）。
- 一份验算清单：C01~C19 每条，用一句话写出「这条数据能让它算出什么数」，确保没有测例因为缺数据而降级。澄清/拒答类（C09/C10/C11/C12/C18/C19）标注「无数据依赖，走澄清/拒答」。
- 不要执行任何 INSERT，只交付 CSV + 说明。

```
人审：时间窗是否都覆盖且数值有差异；转化分母是否来自 UV 表而非订单表；退货是否按发生时间归期；新老客能否闭合；有没有造了禁止的表数据。

---

## 第 3 轮・在 Supabase 搭建 data schema 并导入

```text
本轮在 Supabase 上建表并导入第 2 轮的 CSV。需要用户提供 Supabase 连接信息（不要写进仓库，只在会话里用）。

前置：用户提供以下信息（任一缺失先问，不要猜）：
- Supabase 项目的直连数据库连接串（Settings → Database → Connection string → URI 格式，带 ?sslmode=require）
- 或者：host / port / dbname / user / password 四项
- 确认该项目已启用 pgvector 扩展（Settings → Database → Extensions）

约束：
1. 所有操作只碰 data schema，不碰 app schema（app 由后端 ORM 管）、不碰 public（Supabase 自带）。
2. Supabase 不能建超级用户角色。只读角色 chatbi_ro 用 `CREATE ROLE chatbi_ro NOLOGIN; GRANT SELECT ON ...` 创建；如果 Supabase 限制建角色，跳过角色创建，直接用主连接串跑后续步骤，但要在交付里标注「未建只读角色，生产需补」。
3. 执行顺序：
   a. 执行 backend/infra/init.sql 里的 `CREATE SCHEMA IF NOT EXISTS data;` 部分（只建 schema 和授权，不建表）。
   b. 执行第 1 轮交付的 DDL（即 backend/seed/schema.sql，含 CREATE TABLE + COMMENT + 索引）。该文件开头有 DROP TABLE IF EXISTS，可重复执行。
   c. 导入第 2 轮的 CSV（位于 backend/seed/data/，文件名 = 表名.csv）：用 Supabase Table Editor 的 Import 功能，或 `\copy data.xxx FROM '...csv' WITH (FORMAT csv, HEADER true)`（服务端 COPY 需要 superuser，Supabase 一般用客户端 \copy）。
   d. 每张表导入后立刻 `SELECT COUNT(*) FROM data.xxx;` 确认行数与第 2 轮数据设计说明一致。
4. 导入失败处理：如果某张表导入报错，先看是列名不匹配、类型不匹配、还是外键约束。修 CSV 或修 DDL，不要跳过错表继续。
5. 不跑任何算法、不启动后端、不启动前端。本轮只跟 Supabase SQL Editor 交互。

交付（等人确认后再进入第 4 轮）：

- 一张导入结果表：表名 / 预期行数 / 实际行数 / 状态（成功/失败+原因）。
- 建表和导入过程中遇到的 Supabase 兼容性问题及解决方式（如角色创建受限、COPY 权限等）。

```
人审：所有表行数是否与 CSV 一致；有没有表导入失败未处理；data schema 干净（没有误建到 public）。

---

## 第 4 轮・验证库是否可用（只验库，不跑完整 ChatBI）

```text
本轮只验证数据库本身能否被 ChatBI 的 L0 和 QueryRunner 正常使用，不启动后端、不启动前端、不调算法。

验证手段：直接在 Supabase SQL Editor 或本地 psycopg 脚本里跑下面的 SQL，逐条确认。

前置：第 1 轮的 DDL 和第 2 轮的数据已全部导入 Supabase。

验证项：

> 以下 SQL 中的表名、列名均为占位，按第 1 轮 DDL 实际命名替换。常见对应关系（以第 1 轮最低业务表为准）：订单主表 `data.order_main`（order_id / order_date / channel / customer_id / store_id / order_status / pay_amount）、流量表 `data.traffic_daily`（stat_date / channel / uv / pv）、退货表 `data.refund`（refund_id / refund_date / order_id / refund_amount / doc_type）、客户表 `data.customer`（customer_id / first_pay_date）、活动表 `data.promotion`（id / start_date / end_date）、活动门店关联 `data.promotion_store`（promotion_id / store_id）。

一、L0 元数据可读（对应算法 §4.2 L0 是唯一硬依赖）
1. 跑：`SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema='data' ORDER BY table_name, ordinal_position;`
   过：返回所有表所有列，列名和类型与第 1 轮 DDL 一致。
2. 跑：`SELECT table_name, column_name, col_description(format('data.%I', table_name)::regclass::oid, ordinal_position) AS comment FROM information_schema.columns WHERE table_schema='data';`
   过：每张表每列都有中文 COMMENT，没有 null。这是 L0 抽注释给算法用的关键。
3. 跑：`SELECT MIN(order_date), MAX(order_date) FROM data.order_main;`（表名/列名按第 1 轮实际命名）
   过：日期范围覆盖 2025-06-01 ~ 2026-06-25，C13 超范围拒答的依据。

二、关键指标可算（对应测例 C01~C19 的事实层）
4. GMV（C01）：`SELECT SUM(pay_amount) FROM data.order_main WHERE order_status='paid' AND order_date BETWEEN '2026-06-16' AND '2026-06-18';`
   过：返回非空数值。
5. 同比（C01）：同样的语句分别跑 2026 和 2025 的 6/16~6/18，两个数都非空且不相等。
6. 转化分母（C03 / C17）：`SELECT SUM(uv) FROM data.traffic_daily WHERE stat_date BETWEEN '2026-06-16' AND '2026-06-18' AND channel='xxx';`
   过：能按渠道拿到 UV，且 UV > 该渠道支付用户数（否则转化率 > 100% 不合理）。
7. 退货率（C05）：`SELECT COUNT(*) FROM data.refund WHERE doc_type='refund' AND refund_date BETWEEN '2026-06-16' AND '2026-06-18';`
   过：有退货数据，且能与支付订单数算出比率。
8. 退款金额（C15）：`SELECT SUM(refund_amount) FROM data.refund WHERE doc_type='return' AND refund_date BETWEEN '2026-06-16' AND '2026-06-18';`
   过：有退款金额，能与 GMV 算出占比（按退款发生时间归期，不是按下单时间）。
9. 新老客（C08）：新老客不靠订单表布尔列，靠客户表 first_pay_date 推导——
   `SELECT COUNT(DISTINCT o.customer_id) FROM data.order_main o JOIN data.customer c ON o.customer_id=c.customer_id WHERE o.order_status='paid' AND o.order_date BETWEEN '2026-06-16' AND '2026-06-18' AND c.first_pay_date BETWEEN '2026-06-16' AND '2026-06-18';`
   过：新客、老客都不为 0，GMV 占比合计 100%。
10. 活动门店（满减活动的门店维度）：`SELECT store_id FROM data.promotion_store WHERE promotion_id IN (SELECT id FROM data.promotion WHERE start_date<='2026-06-16' AND end_date>='2026-06-18');`
    过：能查到大促档期参与的门店列表。

三、时间窗可切（对应测例 C01/C04/C06/C07/C16）
11. 预热期：`SELECT COUNT(*) FROM data.order_main WHERE order_date BETWEEN '2026-06-01' AND '2026-06-15';` > 0
12. 首日：`SELECT COUNT(*) FROM data.order_main WHERE order_date='2026-06-16';` > 0
13. 大促前一周：`SELECT COUNT(*) FROM data.order_main WHERE order_date BETWEEN '2026-06-09' AND '2026-06-15';` > 0
14. 大促后一周：`SELECT COUNT(*) FROM data.order_main WHERE order_date BETWEEN '2026-06-19' AND '2026-06-25';` > 0
15. 大促期按天连续（C07）：`SELECT order_date, COUNT(*) FROM data.order_main WHERE order_date BETWEEN '2026-06-16' AND '2026-06-18' GROUP BY order_date ORDER BY order_date;`
    过：三天都有数据，峰值日可识别。

四、只读连接可用（对应后端 §3.2 物理兜底）
16. 如果第 3 轮成功建了 chatbi_ro 角色，用该角色连接后跑：`SELECT * FROM data.order_main LIMIT 1;`（应成功）和 `CREATE TABLE data.test (id int);`（应失败）。
    过：读成功、写失败。如果没建角色，这步标记「未验证，需补只读角色」。

交付：

- 每条验证项的实际结果（数值或 pass/fail）。
- 若有失败项，列出原因和修复建议（改数据还是改 DDL）。
- 重要：标注后端白名单需要同步更新——第 1 轮的新表名必须加入 backend/app/query/sql_guard.py 的 ALLOWED_TABLES 和 backend/app/query/introspection.py 的 DATA_TABLES，否则算法生成的 SQL 会被物理兜底拦截。这一步不属于本轮「只验库」，但必须在跑 ChatBI 前完成。

```
人审：L0 注释是否齐全；GMV/转化/退货/退款金额/新老客是否都能算出非空且合理的数；预热期/首日/前一周/后一周/大促按天这五个时间窗是否都有数据；只读角色是否验证；白名单更新是否被标注为后续必做。

---

## 四轮全部完成后的待办（不在本 Prompt 范围内，提醒用户）

1. 同步后端白名单：把第 1 轮新表名加入 `backend/app/query/sql_guard.py` 的 `ALLOWED_TABLES` 和 `backend/app/query/introspection.py` 的 `DATA_TABLES`。
2. 更新口径词典：根据新表结构更新 `backend/semantics/metrics.yaml`（可选，增强包，不更新也能跑）。
3. 重新启动后端，验证 `GET /api/health` 和一次 `POST /api/chat/ask` 走通。
4. 按 docs/测例.md 逐条跑 C01~C19，记录通过/失败。


