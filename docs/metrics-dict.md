# 口径词典（由 `backend/semantics/metrics.yaml` 生成，勿手改本文件）

> version `l1-2026.11` ｜ updated_at `2026-11-10` ｜ owner `运营`
> 单一口径来源是 YAML；缺字典时链路降级（`degraded=true`），不拒答。

## 指标

| 指标 | 键 | 一句话口径 | 公式 | 同义词 | 来源表 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| GMV | `gmv` | 支付成功金额，不含取消与退款；按支付日期归期 | `SUM(dwd_payment.pay_amount)` | 成交额、销售额、销售额GMV、交易额 | `dwd_payment` |
| 支付订单数 | `paid_orders` | 支付成功的订单数，同一订单多次支付只计一次；按支付日期归期 | `COUNT(DISTINCT dwd_payment.order_id)` | 订单数、单量、支付单量、成交订单数 | `dwd_payment` |
| 客单价 | `aov` | GMV ÷ 支付订单数 | `gmv / paid_orders` | AOV、平均订单金额、平均客单价 | `dwd_payment` |
| 转化率 | `conversion_rate` | 默认口径为支付转化率：支付订单数 ÷ 访客数（UV）；下单转化率另登记在 ambiguity | `paid_orders / SUM(dwd_exposure_daily.uv)` | 成交转化率、转化 | `dwd_payment`、`dwd_exposure_daily` |
| 退货率 | `return_rate` | 退货单数 ÷ 支付订单数，按退款发生日期归期；库中 doc_type='refund' 即退货单（见 backend/seed/gen_data.py 第 351 行与 schema.sql 注释） | `COUNT(DISTINCT dwd_refund.refund_id) / paid_orders` | 退货比例、退货率 | `dwd_refund`、`dwd_payment` |
| 退款率 | `refund_rate` | 仅退款单据数（不退货）÷ 支付订单数，按退款发生日期归期；库中 doc_type='return' 即仅退款单（147 单） | `COUNT(DISTINCT dwd_refund.refund_id) / paid_orders` | 仅退款率、退款比例 | `dwd_refund`、`dwd_payment` |
| 退款金额占比 | `refund_amount_ratio` | 退款金额 ÷ GMV，按退款发生日期归期；包含退货单（refund）与仅退款单（return）两类单据 | `SUM(dwd_refund.refund_amount) / gmv` | 退款金额比例、退款占比 | `dwd_refund`、`dwd_payment` |
| 新客GMV占比 | `new_customer_gmv_ratio` | 首次支付日期（dim_customer.first_pay_date）落在统计期内的客户贡献 GMV ÷ 总 GMV | `SUM(dwd_payment.pay_amount WHERE dim_customer.first_pay_date BETWEEN :start AND :end) / gmv` | 新客占比、新客GMV比例、新老客占比 | `dwd_payment`、`dim_customer` |

## 多口径登记

| 指标 | 口径 | 公式 | 是否默认 |
| :--- | :--- | :--- | :--- |
| 转化率 | 支付转化 | `paid_orders / SUM(dwd_exposure_daily.uv)` | 是 |
| 转化率 | 下单转化 | `COUNT(DISTINCT dwd_order.order_id) / SUM(dwd_exposure_daily.exposure_count)` | 否 |
| 退货率 | 按单数 | `COUNT(DISTINCT dwd_refund.refund_id) / paid_orders` | 是 |
| 退货率 | 按金额 | `SUM(dwd_refund.refund_amount) / gmv` | 否 |

## 维度

| 维度 | 键 | 列 | 维表 | 取值列 | 展示列 | 同义词 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 渠道 | `channel` | `dwd_payment.channel_code` | `dim_channel` | `channel_code` | `channel_name` | 渠道、来源、平台 |
| 类目 | `category` | `dwd_order_detail.category_id` | `dim_category` | `category_id` | `category_name` | 类目、品类、商品类目 |
| 日期 | `date` | `dwd_payment.pay_date` | `—` | `—` | `—` | 日期、时间、每天、按天 |
| 新老客 | `is_new_customer` | `dim_customer.first_pay_date` | `—` | `—` | `—` | 新老客、新客、老客 |

## 大促日历

档期只从 `dim_promotion` 取，不硬编码日期：按 `promotion_type` 过滤，窗口取 `start_date` ~ `end_date`。

库里实际出现的类型：大促、预热（无「日常」行，日常期按不在任何档期内推导）。

| 档期 | 类型 | 开始 | 结束 | 采样时间 |
| :--- | :--- | :--- | :--- | :--- |
| 2025年618大促 | 大促 | 2025-06-16 | 2025-06-18 | 2026-11-10 |
| 2026年618预热 | 预热 | 2026-06-01 | 2026-06-15 | 2026-11-10 |
| 2026年618大促 | 大促 | 2026-06-16 | 2026-06-18 | 2026-11-10 |

相对时间规则：

- `last_week`：本期结束日往前推 7 天，长度与本期一致
- `last_month`：上月同期，按日对齐
- `wow`：上一周期，长度与本期一致、首尾相接
- `yoy`：去年同期，按日对齐

## 未决项

- **dim_promotion.promotion_type 实测无「日常」**：schema.sql 注释写「大促/预热/日常」，实测 DISTINCT 仅 大促、预热；日常期需按「不在任何档期内」推导，词典不硬编码日期
- **dwd_payment.pay_status 实测无 failed**：schema.sql 注释写「success/failed/refunded」，实测 DISTINCT 为 success(9281)、refunded(201)；GMV 口径只认 success
- **doc_type 语义与旧文档相反，已按库中数据纠正**：schema.sql 注释与 gen_data.py 第 351 行一致：refund=退货单（571 单，653559.71）、return=仅退款单（147 单，201991.54）；SDD §5.3 与旧版 metrics.yaml 写反，本版以数据为准
- **seed.verify 的退货率分母与本词典不一致**：backend/seed/seed.py 用 order_status IN ('created','paid','refunded') 作分母（9804 单），算出 5.82%；本词典用支付成功订单数（9281 单），算出 6.15%。本词典口径更严，seed.py 的 verify 仅作跑通校验，不改数据
