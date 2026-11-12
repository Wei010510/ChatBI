"""电商演示库种子数据生成器（支撑 docs/测例.md C01~C19）。

转化漏斗：曝光(dwd_exposure_daily) → 下单(dwd_order) → 支付(dwd_payment) → 退货(dwd_refund)
- 下单转化率 = 下单量 / 曝光量
- 支付转化率 = 支付量 / 下单量
- GMV = dwd_payment 中 pay_status='success' 的 pay_amount

产出 CSV 到 backend/seed/data/，文件名 = 表名.csv。
用法：python -m seed.gen_data
幂等：固定 random seed，重复运行结果一致。
"""
import csv
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# ============ 常量 ============
CHANNELS = [
    ("app", "APP", "online"),
    ("mini_app", "小程序", "online"),
    ("web", "官网", "online"),
    ("offline", "线下门店", "offline"),
]
# 渠道订单权重：app 最高，web 最低（GMV 排名明确，不并列）
CHANNEL_ORDER_WEIGHTS = {"app": 0.40, "mini_app": 0.30, "web": 0.12, "offline": 0.18}
# 渠道曝光倍率：曝光量 = 下单量 × 倍率（保证下单转化率 < 100%）
# web 倍率最高 → 下单转化率最低（C03「掉得最多」）
CHANNEL_EXPOSURE_MULT = {"app": 22, "mini_app": 28, "web": 70, "offline": 12}

CATEGORIES = [
    ("c1", "服饰"),
    ("c2", "数码"),
    ("c3", "食品"),
    ("c4", "家居"),
    ("c5", "美妆"),
    ("c6", "母婴"),
]
# 类目退货率（退货单数/支付单数）：美妆、服饰 > 8%（C05）
# 注意：脚本中 20% 退款单为 return（仅退款），不计入 refund 退货率分子，故配置值需高于目标
CATEGORY_RETURN_RATE = {"c1": 0.13, "c2": 0.03, "c3": 0.02, "c4": 0.05, "c5": 0.16, "c6": 0.04}
CATEGORY_WEIGHTS = {"c1": 0.25, "c2": 0.20, "c3": 0.15, "c4": 0.15, "c5": 0.15, "c6": 0.10}
CATEGORY_PRICE_RANGE = {
    "c1": (59, 599), "c2": (199, 4999), "c3": (19, 299),
    "c4": (39, 899), "c5": (49, 699), "c6": (29, 499),
}

# 成本项占实付金额的比例区间（9 项之和控制在 66%~94.5%，保证有利润）
COST_RATIOS = {
    "product_cost": (0.45, 0.55),
    "first_leg_fee": (0.02, 0.03),
    "warehouse_fee": (0.015, 0.025),
    "last_leg_fee": (0.03, 0.05),
    "ad_fee": (0.08, 0.14),
    "commission_fee": (0.04, 0.07),
    "after_sale_fee": (0.01, 0.025),
    "labor_fee": (0.02, 0.04),
    "adjustment_fee": (-0.005, 0.015),
}
# 广告归因 GMV 占总 GMV 的比例（大促期投放更猛，自然流量占比更低）
AD_GMV_RATIO_PROMO = 0.50
AD_GMV_RATIO_NORMAL = (0.32, 0.45)

PROMO_START, PROMO_END = date(2026, 6, 16), date(2026, 6, 18)
PREHEAT_START, PREHEAT_END = date(2026, 6, 1), date(2026, 6, 15)
POST_START, POST_END = date(2026, 6, 19), date(2026, 6, 25)
LY_PROMO = (date(2025, 6, 16), date(2025, 6, 18))
DATA_START, DATA_END = date(2025, 6, 1), date(2026, 6, 25)

PRODUCTS_PER_CATEGORY = 8
NUM_STORES = 12
NUM_CUSTOMERS = 3000
TARGET_ORDERS = 10000


def day_factor(d: date) -> float:
    """根据日期返回订单量倍率。"""
    if PROMO_START <= d <= PROMO_END:
        return 5.5
    if PREHEAT_START <= d <= PREHEAT_END:
        return 2.2
    if POST_START <= d <= POST_END:
        return 1.6
    if LY_PROMO[0] <= d <= LY_PROMO[1]:
        return 3.8  # 去年同期低于今年，保证同比正增长
    if date(2025, 6, 1) <= d <= date(2025, 6, 15):
        return 1.5
    if date(2025, 6, 19) <= d <= date(2025, 6, 25):
        return 1.3
    return 1.0


def daterange(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def weighted_choice(weight_map: dict):
    keys = list(weight_map.keys())
    weights = [weight_map[k] for k in keys]
    return random.choices(keys, weights=weights, k=1)[0]


# ============ 维度表 ============
def gen_dim_channel():
    rows = [("channel_code", "channel_name", "channel_type")]
    for code, name, ctype in CHANNELS:
        rows.append((code, name, ctype))
    return rows


def gen_dim_category():
    rows = [("category_id", "category_name")]
    for cid, name in CATEGORIES:
        rows.append((cid, name))
    return rows


def gen_dim_product():
    rows = [("product_id", "product_name", "category_id", "base_price")]
    pid = 1
    for cid, cname in CATEGORIES:
        lo, hi = CATEGORY_PRICE_RANGE[cid]
        for i in range(PRODUCTS_PER_CATEGORY):
            price = round(random.uniform(lo, hi), 2)
            rows.append((f"p{pid:04d}", f"{cname}商品{i+1}", cid, price))
            pid += 1
    return rows


def gen_dim_customer():
    """客户先生成，first_pay_date 留空，由支付生成阶段回填。"""
    rows = [("customer_id", "first_pay_date", "register_channel", "city")]
    cities = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京"]
    for i in range(1, NUM_CUSTOMERS + 1):
        reg_ch = weighted_choice(CHANNEL_ORDER_WEIGHTS)
        rows.append((f"cu{i:06d}", "", reg_ch, random.choice(cities)))
    return rows


def gen_dim_store():
    rows = [("store_id", "store_name", "channel_code", "city")]
    cities = ["北京", "上海", "广州", "深圳", "杭州", "成都"]
    for i in range(1, NUM_STORES + 1):
        if i <= 10:
            ch = "offline"
            rows.append((f"s{i:03d}", f"线下门店{i:02d}", ch, random.choice(cities)))
        else:
            ch = random.choice(["app", "mini_app", "web"])
            rows.append((f"s{i:03d}", f"线上{ch}仓", ch, ""))
    return rows


def gen_dim_promotion():
    rows = [("promotion_id", "promotion_name", "promotion_type",
             "start_date", "end_date", "discount_type", "threshold_amount", "discount_amount")]
    rows.append(("promo_618_2026", "2026年618大促", "大促",
                 "2026-06-16", "2026-06-18", "满减", 300, 50))
    rows.append(("preheat_2026", "2026年618预热", "预热",
                 "2026-06-01", "2026-06-15", "满减", 200, 20))
    rows.append(("promo_618_2025", "2025年618大促", "大促",
                 "2025-06-16", "2025-06-18", "满减", 300, 50))
    return rows


def gen_promotion_store(stores):
    """线下门店全部参与大促和预热；线上仓不参与。"""
    rows = [("promotion_id", "store_id")]
    offline_stores = [s[0] for s in stores[1:] if s[2] == "offline"]
    for pid in ["promo_618_2026", "preheat_2026", "promo_618_2025"]:
        for sid in offline_stores:
            rows.append((pid, sid))
    return rows


# ============ 事实表 ============
def distribute_orders_by_day() -> dict:
    """按 day_factor 把 TARGET_ORDERS 分配到每天。"""
    days = list(daterange(DATA_START, DATA_END))
    factors = {d: day_factor(d) for d in days}
    total_factor = sum(factors.values())
    orders_per_day = {}
    remaining = TARGET_ORDERS
    for i, d in enumerate(days):
        if i == len(days) - 1:
            orders_per_day[d] = remaining
        else:
            n = max(0, round(TARGET_ORDERS * factors[d] / total_factor))
            orders_per_day[d] = n
            remaining -= n
    return orders_per_day


def gen_facts(customers, products, stores):
    """生成曝光、下单、订单明细、支付、退货。"""
    customer_ids = [r[0] for r in customers[1:]]
    customer_first_pay = {cid: None for cid in customer_ids}
    products_by_cat = {}
    for r in products[1:]:
        products_by_cat.setdefault(r[2], []).append(r)
    store_ids_offline = [r[0] for r in stores[1:] if r[2] == "offline"]
    store_ids_online = {ch: [r[0] for r in stores[1:] if r[2] == ch]
                        for ch in ["app", "mini_app", "web"]}

    # 表头：与 schema.sql 字段顺序一致
    exposure = [("stat_date", "channel_code", "exposure_count", "uv", "pv", "session_count")]
    orders = [("order_id", "order_date", "customer_id", "store_id", "channel_code",
               "order_status", "total_amount", "discount_amount", "promotion_id")]
    details = [("detail_id", "order_id", "product_id", "category_id",
                "quantity", "unit_price", "amount")]
    payments = [("payment_id", "pay_date", "order_id", "customer_id",
                "channel_code", "pay_amount", "pay_status")]
    refunds = [("refund_id", "refund_date", "payment_id", "order_id", "detail_id",
                "product_id", "category_id", "doc_type", "refund_amount",
                "refund_quantity", "reason")]
    costs = [("cost_id", "order_id", "payment_id", "cost_date",
              "product_cost", "first_leg_fee", "warehouse_fee", "last_leg_fee",
              "ad_fee", "commission_fee", "after_sale_fee", "labor_fee",
              "adjustment_fee", "total_cost", "profit")]
    ads = [("stat_date", "channel_code", "ad_spend", "ad_gmv",
            "ad_order_count", "ad_click", "ad_impression")]

    orders_per_day = distribute_orders_by_day()
    order_seq = 1
    detail_seq = 1
    payment_seq = 1
    refund_seq = 1
    cost_seq = 1
    # 广告表汇总：仅统计支付成功订单（与 GMV 口径一致）
    ad_gmv_by_day_ch = defaultdict(float)
    ad_orders_by_day_ch = defaultdict(int)
    ad_fee_by_day_ch = defaultdict(float)

    for d, n_orders in orders_per_day.items():
        if n_orders <= 0:
            continue
        day_channel_order_counts = {ch: 0 for ch, _, _ in CHANNELS}

        for _ in range(n_orders):
            ch = weighted_choice(CHANNEL_ORDER_WEIGHTS)
            day_channel_order_counts[ch] += 1
            cid = random.choice(customer_ids)

            if ch == "offline":
                sid = random.choice(store_ids_offline)
            else:
                sid = random.choice(store_ids_online[ch]) if store_ids_online.get(ch) else ""

            # 订单状态：约 92% paid, 3% created(已下单未付), 3% cancelled, 2% refunded
            r = random.random()
            if r < 0.92:
                ostatus = "paid"
            elif r < 0.95:
                ostatus = "created"
            elif r < 0.98:
                ostatus = "cancelled"
            else:
                ostatus = "refunded"

            # 明细 1~3 行
            n_items = random.randint(1, 3)
            total = 0.0
            detail_rows = []
            primary_cat = None
            for _ in range(n_items):
                cat = weighted_choice(CATEGORY_WEIGHTS)
                if primary_cat is None:
                    primary_cat = cat
                prod = random.choice(products_by_cat[cat])
                pid, pname, pcat, base_price = prod
                qty = random.randint(1, 3)
                price = round(float(base_price) * random.uniform(0.9, 1.1), 2)
                amt = round(price * qty, 2)
                total += amt
                detail_rows.append((f"dt{detail_seq:07d}", pid, cat, qty, price, amt))
                detail_seq += 1

            # 优惠：大促期/预热期有满减
            promo_id = ""
            discount = 0.0
            if PROMO_START <= d <= PROMO_END:
                promo_id = "promo_618_2026"
                if total >= 300:
                    discount = 50.0
            elif PREHEAT_START <= d <= PREHEAT_END:
                promo_id = "preheat_2026"
                if total >= 200:
                    discount = 20.0
            elif LY_PROMO[0] <= d <= LY_PROMO[1]:
                promo_id = "promo_618_2025"
                if total >= 300:
                    discount = 50.0

            pay_amt = round(max(0.0, total - discount), 2)
            oid = f"o{order_seq:08d}"
            order_seq += 1
            orders.append((oid, d.isoformat(), cid, sid, ch, ostatus,
                           round(total, 2), round(discount, 2), promo_id))

            for dr in detail_rows:
                details.append((dr[0], oid, dr[1], dr[2], dr[3], dr[4], dr[5]))

            # 支付记录：已支付订单才生成支付单
            pay_id = ""
            if ostatus in ("paid", "refunded"):
                pay_id = f"pm{payment_seq:08d}"
                payment_seq += 1
                pay_status = "success" if ostatus == "paid" else "refunded"
                # 支付日期 = 下单日 + 0~1 天
                pay_date = d + timedelta(days=random.randint(0, 1))
                payments.append((pay_id, pay_date.isoformat(), oid, cid, ch, pay_amt, pay_status))
                # 回填客户首次支付日期
                if customer_first_pay[cid] is None or pay_date < customer_first_pay[cid]:
                    customer_first_pay[cid] = pay_date
                # 成本拆解：已支付（含已退款）订单均发生成本
                cost_vals = {
                    k: round(pay_amt * random.uniform(lo, hi), 2)
                    for k, (lo, hi) in COST_RATIOS.items()
                }
                total_cost = round(sum(cost_vals.values()), 2)
                profit = round(pay_amt - total_cost, 2)
                costs.append((
                    f"cs{cost_seq:08d}", oid, pay_id, pay_date.isoformat(),
                    cost_vals["product_cost"], cost_vals["first_leg_fee"],
                    cost_vals["warehouse_fee"], cost_vals["last_leg_fee"],
                    cost_vals["ad_fee"], cost_vals["commission_fee"],
                    cost_vals["after_sale_fee"], cost_vals["labor_fee"],
                    cost_vals["adjustment_fee"], total_cost, profit,
                ))
                cost_seq += 1
                # 广告归因汇总（仅支付成功计入 GMV 口径）
                if pay_status == "success":
                    key = (pay_date, ch)
                    ad_gmv_by_day_ch[key] += pay_amt
                    ad_orders_by_day_ch[key] += 1
                    ad_fee_by_day_ch[key] += cost_vals["ad_fee"]

            # 退货：按主类目退货率决定，只对已支付订单
            if ostatus in ("paid", "refunded"):
                if random.random() < CATEGORY_RETURN_RATE.get(primary_cat, 0.05):
                    ref_date = d + timedelta(days=random.randint(1, 7))
                    if ref_date > DATA_END:
                        ref_date = DATA_END
                    doc = "refund" if random.random() < 0.8 else "return"
                    chosen = random.choice(detail_rows)
                    ref_amt = chosen[5] if doc == "refund" else round(pay_amt * 0.5, 2)
                    refunds.append((f"rf{refund_seq:08d}", ref_date.isoformat(), pay_id,
                                    oid, chosen[0], chosen[1], chosen[2], doc, ref_amt, chosen[3],
                                    random.choice(["质量问题", "不想要了", "尺寸不合适", "发错货"])))
                    refund_seq += 1

        # 曝光表：曝光量 = 下单量 × 渠道倍率（保证下单转化率 < 100%）
        for ch, cnt in day_channel_order_counts.items():
            if cnt == 0:
                exposure_count = random.randint(50, 200)
            else:
                exposure_count = max(cnt + 1, int(cnt * CHANNEL_EXPOSURE_MULT[ch] * random.uniform(0.8, 1.2)))
            uv = int(exposure_count * random.uniform(0.3, 0.6))
            pv = int(exposure_count * random.uniform(2.5, 4.5))
            sessions = int(exposure_count * random.uniform(0.4, 0.7))
            exposure.append((d.isoformat(), ch, exposure_count, uv, pv, sessions))

    # 广告投放日表：广告 GMV = 当日该渠道 GMV × 广告占比；广告花费来自订单广告费分摊
    for (pd, pch), day_gmv in sorted(ad_gmv_by_day_ch.items()):
        if PROMO_START <= pd <= PROMO_END:
            ad_ratio = AD_GMV_RATIO_PROMO
        else:
            ad_ratio = random.uniform(*AD_GMV_RATIO_NORMAL)
        ad_gmv = round(day_gmv * ad_ratio, 2)
        ad_orders = max(1, int(ad_orders_by_day_ch[(pd, pch)] * ad_ratio))
        ad_spend = round(max(0.0, ad_fee_by_day_ch[(pd, pch)] * random.uniform(0.95, 1.05)), 2)
        cpc = random.uniform(2.0, 4.0)
        ad_click = max(1, int(ad_spend / cpc))
        ad_impression = int(ad_click / random.uniform(0.03, 0.08))
        ads.append((pd.isoformat(), pch, ad_spend, ad_gmv, ad_orders, ad_click, ad_impression))

    # 回填客户 first_pay_date
    for i, row in enumerate(customers):
        if i == 0:
            continue
        cid = row[0]
        fp = customer_first_pay.get(cid)
        customers[i] = (cid, fp.isoformat() if fp else "", row[2], row[3])

    return exposure, orders, details, payments, refunds, costs, ads


# ============ 写出 ============
def write_csv(name: str, rows):
    path = DATA_DIR / f"{name}.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerows(rows)
    print(f"{name}: {len(rows)-1} 行")


def main():
    channels = gen_dim_channel()
    categories = gen_dim_category()
    products = gen_dim_product()
    customers = gen_dim_customer()
    stores = gen_dim_store()
    promotions = gen_dim_promotion()
    promo_store = gen_promotion_store(stores)

    exposure, orders, details, payments, refunds, costs, ads = gen_facts(customers, products, stores)

    write_csv("dim_channel", channels)
    write_csv("dim_category", categories)
    write_csv("dim_product", products)
    write_csv("dim_customer", customers)
    write_csv("dim_store", stores)
    write_csv("dim_promotion", promotions)
    write_csv("promotion_store", promo_store)
    write_csv("dwd_exposure_daily", exposure)
    write_csv("dwd_order", orders)
    write_csv("dwd_order_detail", details)
    write_csv("dwd_payment", payments)
    write_csv("dwd_refund", refunds)
    write_csv("dwd_order_cost", costs)
    write_csv("dwd_ad_daily", ads)

    print("\n=== 数据分布自检 ===")
    # 大促期分渠道 GMV（从 payment 表算）
    promo_gmv = defaultdict(float)
    for r in payments[1:]:
        if r[1] >= "2026-06-16" and r[1] <= "2026-06-18" and r[6] == "success":
            promo_gmv[r[4]] += float(r[5])
    print("大促期分渠道 GMV:", dict(sorted(promo_gmv.items(), key=lambda x: -x[1])))

    # 下单转化率（大促期，下单量/曝光量）
    promo_orders = defaultdict(int)
    for r in orders[1:]:
        if r[1] >= "2026-06-16" and r[1] <= "2026-06-18" and r[5] != "cancelled":
            promo_orders[r[4]] += 1
    promo_exposure = defaultdict(int)
    for r in exposure[1:]:
        if r[0] >= "2026-06-16" and r[0] <= "2026-06-18":
            promo_exposure[r[1]] += int(r[2])
    print("大促期下单转化率:")
    for ch in ["app", "mini_app", "web", "offline"]:
        rate = promo_orders[ch] / promo_exposure[ch] * 100 if promo_exposure[ch] else 0
        print(f"  {ch}: 下单={promo_orders[ch]} 曝光={promo_exposure[ch]} 转化率={rate:.2f}%")

    # 类目退货率
    order_cat = {}
    for r in details[1:]:
        if r[1] not in order_cat:
            order_cat[r[1]] = r[3]
    paid_orders = {r[0] for r in orders[1:] if r[5] in ("paid", "refunded")}
    paid_by_cat = defaultdict(int)
    for oid in paid_orders:
        paid_by_cat[order_cat.get(oid, "?")] += 1
    refund_by_cat = defaultdict(int)
    for r in refunds[1:]:
        if r[7] == "refund":
            refund_by_cat[r[6]] += 1
    print("类目退货率:", {c: round(refund_by_cat[c] / paid_by_cat[c] * 100, 1) for c in paid_by_cat})

    # 广告效率（大促期）
    ad_spend_sum = sum(float(r[2]) for r in ads[1:] if "2026-06-16" <= r[0] <= "2026-06-18")
    ad_gmv_sum = sum(float(r[3]) for r in ads[1:] if "2026-06-16" <= r[0] <= "2026-06-18")
    total_gmv_promo = sum(float(r[5]) for r in payments[1:]
                          if "2026-06-16" <= r[1] <= "2026-06-18" and r[6] == "success")
    print(f"广告: 花费={ad_spend_sum:.0f} 广告GMV={ad_gmv_sum:.0f} 总GMV={total_gmv_promo:.0f}")
    if ad_gmv_sum and total_gmv_promo:
        print(f"  ACOS={ad_spend_sum/ad_gmv_sum*100:.1f}%  TCOS={ad_spend_sum/total_gmv_promo*100:.1f}%  "
              f"自然GMV占比={(1-ad_gmv_sum/total_gmv_promo)*100:.1f}%")

    # 成本与利润（大促期）
    cost_sum = sum(float(r[13]) for r in costs[1:] if "2026-06-16" <= r[3] <= "2026-06-18")
    profit_sum = sum(float(r[14]) for r in costs[1:] if "2026-06-16" <= r[3] <= "2026-06-18")
    if cost_sum + profit_sum:
        print(f"成本: 总成本={cost_sum:.0f} 利润={profit_sum:.0f}  "
              f"利润率={profit_sum/(cost_sum+profit_sum)*100:.1f}%")


if __name__ == "__main__":
    main()
