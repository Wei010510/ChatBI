# 电商演示库 · ER 说明与 C01~C19 对照表

> 配套 `backend/seed/schema.sql`。表全部在 `data` schema。

## 一、表清单与职责

| 表名 | 类型 | 职责 |
| :--- | :--- | :--- |
| `dim_channel` | 维 | 渠道（app / mini_app / web / offline） |
| `dim_category` | 维 | 商品类目（服饰/数码/食品/家居/美妆/母婴） |
| `dim_product` | 维 | 商品，挂类目 |
| `dim_customer` | 维 | 客户，含 `first_pay_date`（新老客判定） |
| `dim_store` | 维 | 门店，挂渠道 |
| `dim_promotion` | 维 | 活动档期，含满减门槛/优惠金额 |
| `promotion_store` | 关联 | 活动 × 参与门店 |
| `dwd_exposure_daily` | 事实 | 曝光/访问日表（日×渠道），`exposure_count`——**下单转化率分母** |
| `dwd_order` | 事实 | 下单事实表，含渠道/客户/门店/状态/订单金额——**下单转化率分子 + 支付转化率分母** |
| `dwd_order_detail` | 事实 | 订单明细，含商品/类目/数量/金额 |
| `dwd_payment` | 事实 | 支付事实表，`pay_amount`——**支付转化率分子 + GMV 来源** |
| `dwd_refund` | 事实 | 退货/退款，挂支付单，`doc_type` 区分退货(refund)/退款(return)，按 `refund_date` 归期 |
| `dwd_ad_daily` | 事实 | 广告投放日表（日×渠道），`ad_spend` / `ad_gmv`——**区分自然流量 GMV 与广告 GMV，算 ACOS/TCOS** |
| `dwd_order_cost` | 事实 | 订单成本拆解（按支付订单一条），9 项成本 + `total_cost` + `profit`——**GMV = 总成本 + 利润** |

## 二、关系（ER）

```
dim_category ──< dim_product
dim_channel  ──< dim_store
dim_channel  ──< dwd_exposure_daily
dim_channel  ──< dwd_order
dim_customer ──< dwd_order
dim_store    ──< dwd_order
dim_promotion ──< dwd_order
dim_promotion >── promotion_store ──< dim_store
dwd_order ──< dwd_order_detail >── dim_product
dwd_order ──< dwd_payment
dwd_payment ──< dwd_refund
dwd_order_detail ──< dwd_refund
dim_channel ──< dwd_ad_daily
dwd_order ──< dwd_order_cost >── dwd_payment
```

关键设计：
- **转化漏斗（分子分母各来自不同表）**：
  - 下单转化率 = `dwd_order` 下单量（order_status ≠ 'cancelled'）÷ `dwd_exposure_daily.exposure_count`
  - 支付转化率 = `dwd_payment` 支付量（pay_status='success'）÷ `dwd_order` 下单量
  - GMV = `dwd_payment` 中 pay_status='success' 的 `pay_amount` 合计
- **新老客**：不靠订单布尔列，靠 `dim_customer.first_pay_date` 是否落在查询窗内。
- **退货归期**：`dwd_refund.refund_date`（退款发生日），非下单日；退款挂 `dwd_payment`（退款是支付的逆向）。
- **活动-门店**：`promotion_store` 关联表，订单通过 `store_id` 间接挂到活动。

### 广告与成本口径（扩展指标）

| 指标 | 公式 | 来源 |
| :--- | :--- | :--- |
| 广告 GMV | `SUM(ad_gmv)` | `dwd_ad_daily` |
| 自然流量 GMV | 总 GMV − 广告 GMV | `dwd_payment` − `dwd_ad_daily` |
| ACOS | `SUM(ad_spend) / SUM(ad_gmv)` | `dwd_ad_daily` |
| TCOS | `SUM(ad_spend) / SUM(GMV)` | `dwd_ad_daily` / `dwd_payment` |
| 总成本 | `SUM(total_cost)` | `dwd_order_cost` |
| 利润 | `SUM(profit)` = GMV − 总成本 | `dwd_order_cost` |
| 成本各项 | 直接 SUM 对应列 | `dwd_order_cost` |

- 恒等式：`GMV = 总成本 + 利润`（全量自洽，已校验 `SUM(total_cost+profit) = SUM(pay_amount)`）。
- 成本表覆盖支付成功与已退款订单；若按 `cost_date` 汇总，成本侧 GMV 会略大于 `pay_status='success'` 的 GMV（差额为已退款订单），单看 GMV 仍以 `dwd_payment` 的 success 口径为准。

## 三、C01~C19 对照表

| 测例 | 主要表 | 验算字段/口径 |
| :--- | :--- | :--- |
| **C01** GMV 同比 | `dwd_payment` | `SUM(pay_amount) WHERE pay_status='success'`，2026-06-16~18 vs 2025-06-16~18 |
| **C02** 分渠道 GMV | `dwd_payment`, `dim_channel` | `GROUP BY channel_code`，大促期，排出高低 |
| **C03** 渠道转化率 | `dwd_order`, `dwd_payment`, `dwd_exposure_daily` | 下单转化 = 下单量(dwd_order, status≠cancelled) / 曝光量(exposure_count)；支付转化 = 支付量(dwd_payment, success) / 下单量(dwd_order) |
| **C04** AOV 对比 | `dwd_payment` | AOV = `SUM(pay_amount)/COUNT(success)`，大促期 vs 前一周(6/9~15) |
| **C05** 类目退货率 Top5 | `dwd_refund`, `dwd_order_detail`, `dim_category` | 退货率 = `退货单数(doc_type='refund') / 支付订单数`，按 `category_id` 分组 |
| **C06** 日均 GMV 前后 | `dwd_payment` | 大促期(3天) vs 前一周(7天)，各自 `SUM(pay_amount)/天数` |
| **C07** 大促期按天趋势 | `dwd_payment` | `GROUP BY pay_date`，6/16~18 连续，峰值日可识别 |
| **C08** 新老客 GMV 占比 | `dwd_payment`, `dim_customer` | 新客 = `first_pay_date` 落在窗内；`SUM(pay_amount)` 分新老，合计 100% |
| **C09** 澄清（表现怎么样） | — | 不查数，走澄清，无表依赖 |
| **C10** 澄清（为什么掉了） | — | 不查数，说明只做对照不做因果 |
| **C11** 拒答（竞品） | — | 无竞品表，走拒答 |
| **C12** 拒答（明细导出） | — | 不做明细导出，走拒答 |
| **C13** 拒答（超范围） | `dwd_order` | `MIN(order_date)` = 2025-06-01，2024 年超出范围 |
| **C15** 退款金额占比 | `dwd_refund`, `dwd_payment` | `SUM(refund_amount WHERE doc_type='return') / SUM(pay_amount WHERE pay_status='success')`，按 refund_date 归期 |
| **C16** 环比 | `dwd_payment` | 上周 vs 前一周（等长相邻两周），`SUM(pay_amount)` + 变化率 |
| **C17** 追问（渠道GMV→转化率） | `dwd_payment`, `dwd_order`, `dwd_exposure_daily` | 沿用 C02 时间窗+渠道维度，换指标为转化率（同 C03） |
| **C18** 拒答（写操作） | — | 系统只读，走拒答 |
| **C19** 澄清（缺时间窗） | — | 不查数，追问时间窗 |

## 四、时间窗切法（全部从日期列切，不靠 is_promo）

| 窗口 | 日期范围 | 用途 |
| :--- | :--- | :--- |
| 大促期 | 2026-06-16 ~ 2026-06-18 | C01/C02/C03/C04/C05/C06/C07/C08/C15/C17 |
| 去年同期 | 2025-06-16 ~ 2025-06-18 | C01 同比 |
| 预热期 | 2026-06-01 ~ 2026-06-15 | 单独成窗 |
| 大促前一周 | 2026-06-09 ~ 2026-06-15 | C04/C06 |
| 大促后一周 | 2026-06-19 ~ 2026-06-25 | 回落对比 |
| 首日 | 2026-06-16 | C07 峰值 |
| 数据起点 | 2025-06-01 | C13 超范围拒答 |
