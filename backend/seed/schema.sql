-- 电商演示库 data schema DDL
-- 按 docs/测例.md C01~C19 设计，覆盖 backend/seed/schema.sql
-- 表全部放在 data schema，不碰 app / public
-- 幂等：开头 DROP TABLE IF EXISTS，可重复执行

DROP TABLE IF EXISTS data.dwd_order_cost CASCADE;
DROP TABLE IF EXISTS data.dwd_ad_daily CASCADE;
DROP TABLE IF EXISTS data.dwd_refund CASCADE;
DROP TABLE IF EXISTS data.dwd_payment CASCADE;
DROP TABLE IF EXISTS data.dwd_order_detail CASCADE;
DROP TABLE IF EXISTS data.dwd_order CASCADE;
DROP TABLE IF EXISTS data.dwd_exposure_daily CASCADE;
DROP TABLE IF EXISTS data.promotion_store CASCADE;
DROP TABLE IF EXISTS data.dim_promotion CASCADE;
DROP TABLE IF EXISTS data.dim_store CASCADE;
DROP TABLE IF EXISTS data.dim_product CASCADE;
DROP TABLE IF EXISTS data.dim_category CASCADE;
DROP TABLE IF EXISTS data.dim_customer CASCADE;
DROP TABLE IF EXISTS data.dim_channel CASCADE;

-- ========== 维度表 ==========

-- 渠道维
CREATE TABLE data.dim_channel (
    channel_code TEXT PRIMARY KEY,
    channel_name TEXT NOT NULL,
    channel_type TEXT NOT NULL
);
COMMENT ON TABLE data.dim_channel IS '渠道维度表';
COMMENT ON COLUMN data.dim_channel.channel_code IS '渠道编码（app/mini_app/web/offline）';
COMMENT ON COLUMN data.dim_channel.channel_name IS '渠道名称';
COMMENT ON COLUMN data.dim_channel.channel_type IS '渠道类型（online/offline）';

-- 类目维
CREATE TABLE data.dim_category (
    category_id TEXT PRIMARY KEY,
    category_name TEXT NOT NULL
);
COMMENT ON TABLE data.dim_category IS '商品类目维度表';
COMMENT ON COLUMN data.dim_category.category_id IS '类目ID';
COMMENT ON COLUMN data.dim_category.category_name IS '类目名称（服饰/数码/食品/家居/美妆/母婴）';

-- 商品维
CREATE TABLE data.dim_product (
    product_id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    category_id TEXT NOT NULL REFERENCES data.dim_category(category_id),
    base_price NUMERIC(12, 2) NOT NULL
);
COMMENT ON TABLE data.dim_product IS '商品维度表';
COMMENT ON COLUMN data.dim_product.product_id IS '商品ID';
COMMENT ON COLUMN data.dim_product.product_name IS '商品名称';
COMMENT ON COLUMN data.dim_product.category_id IS '所属类目ID';
COMMENT ON COLUMN data.dim_product.base_price IS '基准售价';

-- 客户维
CREATE TABLE data.dim_customer (
    customer_id TEXT PRIMARY KEY,
    first_pay_date DATE,
    register_channel TEXT,
    city TEXT
);
COMMENT ON TABLE data.dim_customer IS '客户维度表';
COMMENT ON COLUMN data.dim_customer.customer_id IS '客户ID';
COMMENT ON COLUMN data.dim_customer.first_pay_date IS '首次支付成功日期（新老客判定依据）';
COMMENT ON COLUMN data.dim_customer.register_channel IS '注册渠道';
COMMENT ON COLUMN data.dim_customer.city IS '所在城市';

-- 门店维
CREATE TABLE data.dim_store (
    store_id TEXT PRIMARY KEY,
    store_name TEXT NOT NULL,
    channel_code TEXT NOT NULL REFERENCES data.dim_channel(channel_code),
    city TEXT
);
COMMENT ON TABLE data.dim_store IS '门店维度表';
COMMENT ON COLUMN data.dim_store.store_id IS '门店ID';
COMMENT ON COLUMN data.dim_store.store_name IS '门店名称';
COMMENT ON COLUMN data.dim_store.channel_code IS '所属渠道';
COMMENT ON COLUMN data.dim_store.city IS '所在城市';

-- 活动档期（含满减规则）
CREATE TABLE data.dim_promotion (
    promotion_id TEXT PRIMARY KEY,
    promotion_name TEXT NOT NULL,
    promotion_type TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    discount_type TEXT NOT NULL,
    threshold_amount NUMERIC(12, 2),
    discount_amount NUMERIC(12, 2)
);
COMMENT ON TABLE data.dim_promotion IS '活动档期表（含满减规则）';
COMMENT ON COLUMN data.dim_promotion.promotion_id IS '活动ID';
COMMENT ON COLUMN data.dim_promotion.promotion_name IS '活动名称';
COMMENT ON COLUMN data.dim_promotion.promotion_type IS '活动类型（大促/预热/日常）';
COMMENT ON COLUMN data.dim_promotion.start_date IS '活动开始日期';
COMMENT ON COLUMN data.dim_promotion.end_date IS '活动结束日期';
COMMENT ON COLUMN data.dim_promotion.discount_type IS '优惠类型（满减/折扣）';
COMMENT ON COLUMN data.dim_promotion.threshold_amount IS '满减门槛金额';
COMMENT ON COLUMN data.dim_promotion.discount_amount IS '优惠金额';

-- 活动-门店关联
CREATE TABLE data.promotion_store (
    promotion_id TEXT NOT NULL REFERENCES data.dim_promotion(promotion_id),
    store_id TEXT NOT NULL REFERENCES data.dim_store(store_id),
    PRIMARY KEY (promotion_id, store_id)
);
COMMENT ON TABLE data.promotion_store IS '活动参与门店关联表';
COMMENT ON COLUMN data.promotion_store.promotion_id IS '活动ID';
COMMENT ON COLUMN data.promotion_store.store_id IS '参与门店ID';

-- ========== 事实表（转化漏斗：曝光 → 下单 → 支付 → 退货） ==========

-- 曝光/访问表（下单转化率分母）
CREATE TABLE data.dwd_exposure_daily (
    stat_date DATE NOT NULL,
    channel_code TEXT NOT NULL REFERENCES data.dim_channel(channel_code),
    exposure_count INTEGER NOT NULL DEFAULT 0,
    uv INTEGER NOT NULL DEFAULT 0,
    pv INTEGER NOT NULL DEFAULT 0,
    session_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (stat_date, channel_code)
);
COMMENT ON TABLE data.dwd_exposure_daily IS '曝光/访问日表（下单转化率分母，按日×渠道）';
COMMENT ON COLUMN data.dwd_exposure_daily.stat_date IS '统计日期';
COMMENT ON COLUMN data.dwd_exposure_daily.channel_code IS '渠道编码';
COMMENT ON COLUMN data.dwd_exposure_daily.exposure_count IS '曝光量（=访问会话量，下单转化率分母）';
COMMENT ON COLUMN data.dwd_exposure_daily.uv IS '访客数（UV）';
COMMENT ON COLUMN data.dwd_exposure_daily.pv IS '页面浏览量';
COMMENT ON COLUMN data.dwd_exposure_daily.session_count IS '会话数';

-- 下单表（下单转化率分子 + 支付转化率分母）
CREATE TABLE data.dwd_order (
    order_id TEXT PRIMARY KEY,
    order_date DATE NOT NULL,
    customer_id TEXT NOT NULL REFERENCES data.dim_customer(customer_id),
    store_id TEXT REFERENCES data.dim_store(store_id),
    channel_code TEXT NOT NULL REFERENCES data.dim_channel(channel_code),
    order_status TEXT NOT NULL,
    total_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    promotion_id TEXT REFERENCES data.dim_promotion(promotion_id)
);
COMMENT ON TABLE data.dwd_order IS '下单事实表（下单转化率分子 + 支付转化率分母）';
COMMENT ON COLUMN data.dwd_order.order_id IS '订单ID';
COMMENT ON COLUMN data.dwd_order.order_date IS '下单日期';
COMMENT ON COLUMN data.dwd_order.customer_id IS '客户ID';
COMMENT ON COLUMN data.dwd_order.store_id IS '门店ID（线下载有，线上可为空）';
COMMENT ON COLUMN data.dwd_order.channel_code IS '下单渠道';
COMMENT ON COLUMN data.dwd_order.order_status IS '订单状态（created/paid/cancelled/refunded）';
COMMENT ON COLUMN data.dwd_order.total_amount IS '订单原始金额';
COMMENT ON COLUMN data.dwd_order.discount_amount IS '优惠金额';
COMMENT ON COLUMN data.dwd_order.promotion_id IS '关联活动ID';

CREATE INDEX idx_order_date ON data.dwd_order(order_date);
CREATE INDEX idx_order_channel ON data.dwd_order(channel_code);
CREATE INDEX idx_order_customer ON data.dwd_order(customer_id);
CREATE INDEX idx_order_status ON data.dwd_order(order_status);

-- 订单明细
CREATE TABLE data.dwd_order_detail (
    detail_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES data.dwd_order(order_id),
    product_id TEXT NOT NULL REFERENCES data.dim_product(product_id),
    category_id TEXT NOT NULL REFERENCES data.dim_category(category_id),
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL,
    amount NUMERIC(12, 2) NOT NULL
);
COMMENT ON TABLE data.dwd_order_detail IS '订单明细表（事实表）';
COMMENT ON COLUMN data.dwd_order_detail.detail_id IS '明细ID';
COMMENT ON COLUMN data.dwd_order_detail.order_id IS '订单ID';
COMMENT ON COLUMN data.dwd_order_detail.product_id IS '商品ID';
COMMENT ON COLUMN data.dwd_order_detail.category_id IS '类目ID（冗余，便于按类目统计）';
COMMENT ON COLUMN data.dwd_order_detail.quantity IS '购买数量';
COMMENT ON COLUMN data.dwd_order_detail.unit_price IS '成交单价';
COMMENT ON COLUMN data.dwd_order_detail.amount IS '明细金额';

CREATE INDEX idx_order_detail_order ON data.dwd_order_detail(order_id);
CREATE INDEX idx_order_detail_category ON data.dwd_order_detail(category_id);

-- 支付表（支付转化率分子 + GMV 来源）
CREATE TABLE data.dwd_payment (
    payment_id TEXT PRIMARY KEY,
    pay_date DATE NOT NULL,
    order_id TEXT NOT NULL REFERENCES data.dwd_order(order_id),
    customer_id TEXT NOT NULL REFERENCES data.dim_customer(customer_id),
    channel_code TEXT NOT NULL REFERENCES data.dim_channel(channel_code),
    pay_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    pay_status TEXT NOT NULL
);
COMMENT ON TABLE data.dwd_payment IS '支付事实表（支付转化率分子 + GMV 来源）';
COMMENT ON COLUMN data.dwd_payment.payment_id IS '支付单ID';
COMMENT ON COLUMN data.dwd_payment.pay_date IS '支付日期（按此归期）';
COMMENT ON COLUMN data.dwd_payment.order_id IS '关联订单ID';
COMMENT ON COLUMN data.dwd_payment.customer_id IS '客户ID';
COMMENT ON COLUMN data.dwd_payment.channel_code IS '支付渠道';
COMMENT ON COLUMN data.dwd_payment.pay_amount IS '实付金额（GMV 口径 = 支付成功金额）';
COMMENT ON COLUMN data.dwd_payment.pay_status IS '支付状态（success/failed/refunded）';

CREATE INDEX idx_payment_date ON data.dwd_payment(pay_date);
CREATE INDEX idx_payment_channel ON data.dwd_payment(channel_code);
CREATE INDEX idx_payment_customer ON data.dwd_payment(customer_id);
CREATE INDEX idx_payment_status ON data.dwd_payment(pay_status);

-- 退货/退款事实表（挂支付单，退款是支付的逆向）
CREATE TABLE data.dwd_refund (
    refund_id TEXT PRIMARY KEY,
    refund_date DATE NOT NULL,
    payment_id TEXT REFERENCES data.dwd_payment(payment_id),
    order_id TEXT NOT NULL REFERENCES data.dwd_order(order_id),
    detail_id TEXT REFERENCES data.dwd_order_detail(detail_id),
    product_id TEXT REFERENCES data.dim_product(product_id),
    category_id TEXT REFERENCES data.dim_category(category_id),
    doc_type TEXT NOT NULL,
    refund_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    refund_quantity INTEGER NOT NULL DEFAULT 0,
    reason TEXT
);
COMMENT ON TABLE data.dwd_refund IS '退货/退款事实表';
COMMENT ON COLUMN data.dwd_refund.refund_id IS '退款单ID';
COMMENT ON COLUMN data.dwd_refund.refund_date IS '退款发生日期（按此归期，非下单时间）';
COMMENT ON COLUMN data.dwd_refund.payment_id IS '原支付单ID';
COMMENT ON COLUMN data.dwd_refund.order_id IS '原订单ID';
COMMENT ON COLUMN data.dwd_refund.detail_id IS '原订单明细ID';
COMMENT ON COLUMN data.dwd_refund.product_id IS '商品ID';
COMMENT ON COLUMN data.dwd_refund.category_id IS '类目ID';
COMMENT ON COLUMN data.dwd_refund.doc_type IS '单据类型（refund=退货单/return=退款单）';
COMMENT ON COLUMN data.dwd_refund.refund_amount IS '退款金额';
COMMENT ON COLUMN data.dwd_refund.refund_quantity IS '退款数量';
COMMENT ON COLUMN data.dwd_refund.reason IS '退款原因';

CREATE INDEX idx_refund_date ON data.dwd_refund(refund_date);
CREATE INDEX idx_refund_category ON data.dwd_refund(category_id);
CREATE INDEX idx_refund_doctype ON data.dwd_refund(doc_type);

-- 广告投放日表（区分自然流量 GMV 与广告 GMV，算 ACOS / TCOS）
CREATE TABLE data.dwd_ad_daily (
    stat_date DATE NOT NULL,
    channel_code TEXT NOT NULL REFERENCES data.dim_channel(channel_code),
    ad_spend NUMERIC(12, 2) NOT NULL DEFAULT 0,
    ad_gmv NUMERIC(12, 2) NOT NULL DEFAULT 0,
    ad_order_count INTEGER NOT NULL DEFAULT 0,
    ad_click INTEGER NOT NULL DEFAULT 0,
    ad_impression INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (stat_date, channel_code)
);
COMMENT ON TABLE data.dwd_ad_daily IS '广告投放日表（按日×渠道，用于区分自然流量GMV/广告GMV、计算ACOS/TCOS）';
COMMENT ON COLUMN data.dwd_ad_daily.stat_date IS '统计日期';
COMMENT ON COLUMN data.dwd_ad_daily.channel_code IS '投放渠道编码';
COMMENT ON COLUMN data.dwd_ad_daily.ad_spend IS '广告花费（ACOS/TCOS 分子）';
COMMENT ON COLUMN data.dwd_ad_daily.ad_gmv IS '广告归因GMV（ACOS 分母；自然流量GMV = 总GMV - 广告GMV）';
COMMENT ON COLUMN data.dwd_ad_daily.ad_order_count IS '广告归因订单数';
COMMENT ON COLUMN data.dwd_ad_daily.ad_click IS '广告点击数';
COMMENT ON COLUMN data.dwd_ad_daily.ad_impression IS '广告曝光数';

CREATE INDEX idx_ad_daily_date ON data.dwd_ad_daily(stat_date);
CREATE INDEX idx_ad_daily_channel ON data.dwd_ad_daily(channel_code);

-- 订单成本拆解表（GMV = 总成本 + 利润）
CREATE TABLE data.dwd_order_cost (
    cost_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES data.dwd_order(order_id),
    payment_id TEXT REFERENCES data.dwd_payment(payment_id),
    cost_date DATE NOT NULL,
    product_cost NUMERIC(12, 2) NOT NULL DEFAULT 0,
    first_leg_fee NUMERIC(12, 2) NOT NULL DEFAULT 0,
    warehouse_fee NUMERIC(12, 2) NOT NULL DEFAULT 0,
    last_leg_fee NUMERIC(12, 2) NOT NULL DEFAULT 0,
    ad_fee NUMERIC(12, 2) NOT NULL DEFAULT 0,
    commission_fee NUMERIC(12, 2) NOT NULL DEFAULT 0,
    after_sale_fee NUMERIC(12, 2) NOT NULL DEFAULT 0,
    labor_fee NUMERIC(12, 2) NOT NULL DEFAULT 0,
    adjustment_fee NUMERIC(12, 2) NOT NULL DEFAULT 0,
    total_cost NUMERIC(12, 2) NOT NULL DEFAULT 0,
    profit NUMERIC(12, 2) NOT NULL DEFAULT 0
);
COMMENT ON TABLE data.dwd_order_cost IS '订单成本拆解表（GMV = 总成本 + 利润，按支付订单一条）';
COMMENT ON COLUMN data.dwd_order_cost.cost_id IS '成本记录ID';
COMMENT ON COLUMN data.dwd_order_cost.order_id IS '关联订单ID';
COMMENT ON COLUMN data.dwd_order_cost.payment_id IS '关联支付单ID';
COMMENT ON COLUMN data.dwd_order_cost.cost_date IS '成本归期（=支付日期）';
COMMENT ON COLUMN data.dwd_order_cost.product_cost IS '产品成本';
COMMENT ON COLUMN data.dwd_order_cost.first_leg_fee IS '头程费用';
COMMENT ON COLUMN data.dwd_order_cost.warehouse_fee IS '仓租费用';
COMMENT ON COLUMN data.dwd_order_cost.last_leg_fee IS '尾程费用';
COMMENT ON COLUMN data.dwd_order_cost.ad_fee IS '广告费用（分摊）';
COMMENT ON COLUMN data.dwd_order_cost.commission_fee IS '平台佣金';
COMMENT ON COLUMN data.dwd_order_cost.after_sale_fee IS '售后费用';
COMMENT ON COLUMN data.dwd_order_cost.labor_fee IS '人工费用';
COMMENT ON COLUMN data.dwd_order_cost.adjustment_fee IS '调整费（可正可负）';
COMMENT ON COLUMN data.dwd_order_cost.total_cost IS '总成本（上述9项之和，不含利润）';
COMMENT ON COLUMN data.dwd_order_cost.profit IS '利润（=实付GMV - 总成本）';

CREATE INDEX idx_order_cost_order ON data.dwd_order_cost(order_id);
CREATE INDEX idx_order_cost_payment ON data.dwd_order_cost(payment_id);
CREATE INDEX idx_order_cost_date ON data.dwd_order_cost(cost_date);

-- 授权只读角色（若角色不存在会报错，由 infra/init.sql 负责建角色）
-- 先给 schema USAGE，再给表 SELECT，缺 USAGE 时 SELECT 会被拒
GRANT USAGE ON SCHEMA data TO chatbi_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA data TO chatbi_ro;
