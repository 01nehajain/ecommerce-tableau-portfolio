"""
E-Commerce Sales & Customer Analytics — Data Pipeline
=======================================================
Transforms raw transactional exports into a clean star-schema-ready
fact table plus a set of pre-aggregated marts for Tableau.

Run:  python 01_data_pipeline.py
Inputs:  ../data/raw/*.csv
Outputs: ../data/processed/*.csv
"""

import pandas as pd
import numpy as np

RAW = "../data/raw"
OUT = "../data/processed"

pd.set_option("display.width", 140)

# ---------------------------------------------------------------
# 1. LOAD
# ---------------------------------------------------------------
orders = pd.read_csv(f"{RAW}/ecommerce_sales_customer_analytics_150k.csv", low_memory=False)
order_items = pd.read_csv(f"{RAW}/order_items.csv")
products = pd.read_csv(f"{RAW}/product_catalog.csv")
customers = pd.read_csv(f"{RAW}/customer_master.csv")

print(f"orders: {orders.shape} | order_items: {order_items.shape} | "
      f"products: {products.shape} | customers: {customers.shape}")

# ---------------------------------------------------------------
# 2. CLEAN + FEATURE ENGINEER — ORDER-LEVEL FACT TABLE
# ---------------------------------------------------------------
orders["order_date"] = pd.to_datetime(orders["order_date"])
orders["year"] = orders["order_date"].dt.year
orders["quarter"] = orders["order_date"].dt.to_period("Q").astype(str)
orders["month"] = orders["order_date"].dt.to_period("M").astype(str)
orders["month_name"] = orders["order_date"].dt.strftime("%b")
orders["day_of_week"] = orders["order_date"].dt.day_name()
orders["is_weekend"] = orders["order_date"].dt.dayofweek >= 5

# Business flags
orders["is_returned"] = orders["order_status"].eq("Returned")
orders["is_cancelled"] = orders["order_status"].eq("Cancelled")
orders["is_completed"] = orders["order_status"].eq("Completed")
orders["is_late"] = orders["delivery_status"].eq("Late")
orders["net_profit_flag"] = np.where(orders["profit"] >= 0, "Profitable", "Loss-Making")

# Discount tiering (Tableau-friendly bins)
orders["discount_pct_of_gross"] = np.where(
    orders["gross_sales"] > 0, orders["discount_amount"] / orders["gross_sales"] * 100, 0
)
bins = [-0.01, 0, 10, 20, 30, 40, 100]
labels = ["0% (No Discount)", "1-10%", "11-20%", "21-30%", "31-40%", "41%+"]
orders["discount_band"] = pd.cut(orders["discount_pct_of_gross"], bins=bins, labels=labels)

# Delivery performance bucket
orders["delivery_speed_band"] = pd.cut(
    orders["delivery_days"],
    bins=[-0.01, 2, 4, 7, 100],
    labels=["0-2 days", "3-4 days", "5-7 days", "8+ days"],
)

orders.to_csv(f"{OUT}/fact_orders.csv", index=False)
print("-> fact_orders.csv written", orders.shape)

# ---------------------------------------------------------------
# 3. RFM CUSTOMER SEGMENTATION
# ---------------------------------------------------------------
snapshot_date = orders["order_date"].max() + pd.Timedelta(days=1)

completed = orders[orders["is_completed"]]

rfm = completed.groupby("customer_id").agg(
    recency_days=("order_date", lambda x: (snapshot_date - x.max()).days),
    frequency=("order_id", "nunique"),
    monetary=("net_sales", "sum"),
).reset_index()

# Quintile scores (5 = best)
rfm["r_score"] = pd.qcut(rfm["recency_days"], 5, labels=[5, 4, 3, 2, 1]).astype(int)
rfm["f_score"] = pd.qcut(rfm["frequency"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
rfm["m_score"] = pd.qcut(rfm["monetary"], 5, labels=[1, 2, 3, 4, 5]).astype(int)
rfm["rfm_score"] = rfm["r_score"].astype(str) + rfm["f_score"].astype(str) + rfm["m_score"].astype(str)
rfm["rfm_sum"] = rfm[["r_score", "f_score", "m_score"]].sum(axis=1)


def segment(row):
    r, f, m = row["r_score"], row["f_score"], row["m_score"]
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    if r >= 3 and f >= 3 and m >= 3:
        return "Loyal Customers"
    if r >= 4 and f <= 2:
        return "New Customers"
    if r >= 3 and f <= 2 and m <= 3:
        return "Potential Loyalists"
    if r <= 2 and f >= 3 and m >= 3:
        return "At Risk"
    if r <= 2 and f <= 2 and m >= 4:
        return "Cannot Lose Them (High Value, Inactive)"
    if r <= 2 and f <= 2 and m <= 2:
        return "Hibernating / Lost"
    return "Low-Engagement"


rfm["customer_segment_rfm"] = rfm.apply(segment, axis=1)

# join demographics
cust_dim = customers[[
    "customer_id", "customer_age", "gender", "customer_segment",
    "customer_city", "customer_state", "customer_country", "region",
    "customer_acquisition_cost",
]].drop_duplicates("customer_id")

rfm = rfm.merge(cust_dim, on="customer_id", how="left")
rfm.to_csv(f"{OUT}/customer_rfm_segments.csv", index=False)
print("-> customer_rfm_segments.csv written", rfm.shape)

# ---------------------------------------------------------------
# 4. PRODUCT-LEVEL FACT (order_items + product_catalog)
# ---------------------------------------------------------------
items = order_items.merge(
    products[["product_id", "product_name", "product_category", "product_subcategory", "brand", "supplier", "product_rating"]],
    on="product_id", how="left"
)
items = items.merge(
    orders[["order_id", "order_date", "year", "month", "region", "customer_segment", "order_status"]],
    on="order_id", how="left"
)
items["profit_margin_pct"] = np.where(items["net_sales"] > 0, items["profit"] / items["net_sales"] * 100, np.nan)
items.to_csv(f"{OUT}/fact_order_items.csv", index=False)
print("-> fact_order_items.csv written", items.shape)

# ---------------------------------------------------------------
# 5. PRE-AGGREGATED MARTS (for fast Tableau extracts / worksheets)
# ---------------------------------------------------------------

# 5a. Monthly KPI trend
monthly = orders.groupby("month").agg(
    orders_count=("order_id", "nunique"),
    customers=("customer_id", "nunique"),
    gross_sales=("gross_sales", "sum"),
    net_sales=("net_sales", "sum"),
    discount_amount=("discount_amount", "sum"),
    profit=("profit", "sum"),
    returns=("is_returned", "sum"),
    cancellations=("is_cancelled", "sum"),
    avg_rating=("customer_rating", "mean"),
).reset_index()
monthly["profit_margin_pct"] = monthly["profit"] / monthly["net_sales"] * 100
monthly["avg_order_value"] = monthly["net_sales"] / monthly["orders_count"]
monthly["return_rate_pct"] = monthly["returns"] / monthly["orders_count"] * 100
monthly.to_csv(f"{OUT}/agg_monthly_kpis.csv", index=False)

# 5b. Category x Sub-category performance (product-level, true sales lines)
cat_perf = items.groupby(["product_category", "product_subcategory"]).agg(
    units_sold=("quantity", "sum"),
    gross_sales=("gross_sales", "sum"),
    net_sales=("net_sales", "sum"),
    profit=("profit", "sum"),
    orders=("order_id", "nunique"),
).reset_index()
cat_perf["profit_margin_pct"] = cat_perf["profit"] / cat_perf["net_sales"] * 100
cat_perf["revenue_rank"] = cat_perf["net_sales"].rank(ascending=False)
cat_perf["profit_rank"] = cat_perf["profit"].rank(ascending=False)
cat_perf["rank_gap"] = cat_perf["revenue_rank"] - cat_perf["profit_rank"]  # + = looks better on rev than profit
cat_perf.to_csv(f"{OUT}/agg_category_performance.csv", index=False)

# 5c. Brand performance
brand_perf = items.groupby("brand").agg(
    units_sold=("quantity", "sum"),
    net_sales=("net_sales", "sum"),
    profit=("profit", "sum"),
    avg_rating=("product_rating", "mean"),
    orders=("order_id", "nunique"),
).reset_index()
brand_perf["profit_margin_pct"] = brand_perf["profit"] / brand_perf["net_sales"] * 100
brand_perf.to_csv(f"{OUT}/agg_brand_performance.csv", index=False)

# 5d. Region performance
region_perf = orders.groupby("region").agg(
    orders_count=("order_id", "nunique"),
    customers=("customer_id", "nunique"),
    net_sales=("net_sales", "sum"),
    profit=("profit", "sum"),
    avg_delivery_days=("delivery_days", "mean"),
    return_rate=("is_returned", "mean"),
    avg_rating=("customer_rating", "mean"),
).reset_index()
region_perf["profit_margin_pct"] = region_perf["profit"] / region_perf["net_sales"] * 100
region_perf["aov"] = region_perf["net_sales"] / region_perf["orders_count"]
region_perf.to_csv(f"{OUT}/agg_region_performance.csv", index=False)

# 5e. Discount sensitivity (discount band x sales/profit/volume)
disc = orders.groupby("discount_band", observed=True).agg(
    orders_count=("order_id", "nunique"),
    avg_quantity=("quantity", "mean"),
    net_sales=("net_sales", "sum"),
    profit=("profit", "sum"),
    avg_profit_margin=("profit_margin_percentage", "mean"),
).reset_index()
disc.to_csv(f"{OUT}/agg_discount_profitability.csv", index=False)

# 5f. Discount x Category cross tab (profitability heatmap)
disc_cat = orders.merge(
    items[["order_id", "product_category"]].drop_duplicates("order_id"),
    on="order_id", how="left"
).groupby(["product_category", "discount_band"], observed=True).agg(
    net_sales=("net_sales", "sum"),
    profit=("profit", "sum"),
    orders_count=("order_id", "nunique"),
).reset_index()
disc_cat["profit_margin_pct"] = disc_cat["profit"] / disc_cat["net_sales"] * 100
disc_cat.to_csv(f"{OUT}/agg_discount_by_category.csv", index=False)

# 5g. Marketing channel performance + customer value
channel = orders.groupby("marketing_channel").agg(
    orders_count=("order_id", "nunique"),
    customers=("customer_id", "nunique"),
    net_sales=("net_sales", "sum"),
    profit=("profit", "sum"),
    avg_clv=("customer_lifetime_value", "mean"),
    repeat_rate=("is_repeat_customer", "mean"),
).reset_index()
channel["aov"] = channel["net_sales"] / channel["orders_count"]
channel["revenue_per_customer"] = channel["net_sales"] / channel["customers"]
channel.to_csv(f"{OUT}/agg_marketing_channel.csv", index=False)

# 5h. Delivery vs ratings
# NOTE: delivery_days / customer_rating are only populated for Completed orders
# (Cancelled / Pending / Returned orders never reach delivery or get rated), so
# this analysis is intentionally scoped to completed orders only.
completed_only = orders[orders["is_completed"]]
delivery = completed_only.groupby("delivery_status", observed=True).agg(
    orders_count=("order_id", "nunique"),
    avg_delivery_days=("delivery_days", "mean"),
    avg_rating=("customer_rating", "mean"),
    avg_shipping_cost=("shipping_cost", "mean"),
).reset_index()
delivery.to_csv(f"{OUT}/agg_delivery_performance.csv", index=False)

delivery_speed = completed_only.groupby("delivery_speed_band", observed=True).agg(
    orders_count=("order_id", "nunique"),
    avg_rating=("customer_rating", "mean"),
    avg_shipping_cost=("shipping_cost", "mean"),
).reset_index()
delivery_speed.to_csv(f"{OUT}/agg_delivery_speed_band.csv", index=False)

# 5i. Returns deep-dive
returns_df = orders[orders["is_returned"]]
returns_reason = returns_df.groupby("return_reason").agg(
    orders_count=("order_id", "nunique"),
    lost_revenue=("net_sales", "sum"),
).reset_index().sort_values("orders_count", ascending=False)
returns_reason.to_csv(f"{OUT}/agg_return_reasons.csv", index=False)

returns_by_cat = orders.merge(
    items[["order_id", "product_category"]].drop_duplicates("order_id"),
    on="order_id", how="left"
).groupby("product_category").agg(
    orders_count=("order_id", "nunique"),
    returns=("is_returned", "sum"),
).reset_index()
returns_by_cat["return_rate_pct"] = returns_by_cat["returns"] / returns_by_cat["orders_count"] * 100
returns_by_cat.to_csv(f"{OUT}/agg_returns_by_category.csv", index=False)

# 5j. Loyalty tier (customer_segment as proxy) vs behavior
loyalty = orders.groupby("customer_segment").agg(
    customers=("customer_id", "nunique"),
    orders_count=("order_id", "nunique"),
    net_sales=("net_sales", "sum"),
    profit=("profit", "sum"),
    avg_clv=("customer_lifetime_value", "mean"),
    repeat_rate=("is_repeat_customer", "mean"),
    return_rate=("is_returned", "mean"),
).reset_index()
loyalty["aov"] = loyalty["net_sales"] / loyalty["orders_count"]
loyalty.to_csv(f"{OUT}/agg_customer_segment_value.csv", index=False)

# 5k. RFM segment summary (for quadrant / treemap in Tableau)
rfm_summary = rfm.groupby("customer_segment_rfm").agg(
    customers=("customer_id", "nunique"),
    avg_recency=("recency_days", "mean"),
    avg_frequency=("frequency", "mean"),
    avg_monetary=("monetary", "mean"),
    total_monetary=("monetary", "sum"),
).reset_index().sort_values("total_monetary", ascending=False)
rfm_summary.to_csv(f"{OUT}/agg_rfm_segment_summary.csv", index=False)

print("\nAll processed marts written to", OUT)
