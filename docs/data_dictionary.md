# Data Dictionary — `data/processed/`

## Core fact tables

### `fact_orders.csv` (138,116 rows, 1 row = 1 order)
All original columns from the raw source, plus engineered fields:

| Field | Description |
|---|---|
| `year`, `quarter`, `month`, `month_name`, `day_of_week`, `is_weekend` | Calendar features derived from `order_date` |
| `is_returned`, `is_cancelled`, `is_completed` | Boolean flags derived from `order_status` |
| `is_late` | True if `delivery_status` = "Delayed" |
| `net_profit_flag` | "Profitable" / "Loss-Making" based on sign of `profit` |
| `discount_pct_of_gross` | `discount_amount / gross_sales * 100` |
| `discount_band` | Binned discount depth: 0%, 1–10%, 11–20%, 21–30%, 31–40%, 41%+ |
| `delivery_speed_band` | Binned `delivery_days`: 0–2, 3–4, 5–7, 8+ days (completed orders only) |

### `fact_order_items.csv` (397,569 rows, 1 row = 1 product line within an order)
Line-item detail — the only table with true per-product grain. Joins `order_items` + `product_catalog` (name, category, subcategory, brand, supplier, rating) + selected order-level context (`order_date`, `region`, `customer_segment`, `order_status`).

### `customer_rfm_segments.csv` (24,748 rows, 1 row = 1 customer with ≥1 completed order)
| Field | Description |
|---|---|
| `recency_days` | Days between customer's last completed order and the day after the dataset's max order date |
| `frequency` | Count of distinct completed orders |
| `monetary` | Sum of `net_sales` across completed orders |
| `r_score`, `f_score`, `m_score` | Quintile scores 1 (worst) – 5 (best) |
| `rfm_score` | Concatenated string, e.g. "543" |
| `customer_segment_rfm` | Named behavioral segment (Champions, Loyal Customers, At Risk, Hibernating / Lost, New Customers, Potential Loyalists, Cannot Lose Them, Low-Engagement) |
| `customer_segment` | The dataset's original declared tier (Consumer/Premium/VIP/Business) — kept alongside for comparison |

---

## Pre-aggregated marts

| File | Grain | Key measures |
|---|---|---|
| `agg_monthly_kpis.csv` | month | orders, customers, gross/net sales, discount, profit, returns, cancellations, AOV, margin %, return rate % |
| `agg_category_performance.csv` | category × subcategory | units, gross/net sales, profit, margin %, revenue rank, profit rank, `rank_gap` (revenue rank − profit rank; positive = looks better on revenue than on profit) |
| `agg_brand_performance.csv` | brand | units, net sales, profit, margin %, avg product rating |
| `agg_region_performance.csv` | region | orders, customers, net sales, profit, margin %, AOV, avg delivery days, return rate, avg rating |
| `agg_discount_profitability.csv` | discount band | orders, avg quantity, net sales, profit, avg margin % |
| `agg_discount_by_category.csv` | category × discount band | net sales, profit, margin %, orders — for the heatmap |
| `agg_marketing_channel.csv` | marketing channel | orders, customers, net sales, profit, avg CLV, repeat rate, AOV, revenue per customer |
| `agg_delivery_performance.csv` | delivery status (completed orders only) | orders, avg delivery days, avg rating, avg shipping cost |
| `agg_delivery_speed_band.csv` | delivery speed band (completed orders only) | orders, avg rating, avg shipping cost |
| `agg_return_reasons.csv` | return reason | order count, lost revenue (net sales on returned orders) |
| `agg_returns_by_category.csv` | category | orders, returns, return rate % |
| `agg_rfm_segment_summary.csv` | RFM segment | customer count, avg recency/frequency/monetary, total monetary value |
| `agg_customer_segment_value.csv` | declared customer segment | customers, orders, net sales, profit, avg CLV, repeat rate, return rate, AOV |

---

## Known data-quality notes (validate before extending this analysis)

1. `delivery_days`, `estimated_delivery_days`, `delivery_status`, `customer_rating`, `review_sentiment`, `customer_review` are **null for every non-Completed order** (Cancelled, Pending, Returned) — by data design, not missing data. Any delivery/rating analysis in this project is scoped to Completed orders only.
2. `is_repeat_customer` is `True` for 99.8% of orders — not usable as a segmentation variable; the RFM segmentation was built instead.
3. `coupon_code` (80% null) and `campaign_name` (60% null) reflect orders with no coupon/campaign attribution, not missing data — treat null as "no coupon" / "no named campaign," not as an error.
4. Revenue totals in this project's marts (`net_sales`) will not exactly match the publisher's single "Total Revenue" figure in `dataset_statistics.csv`, since that figure is computed on a different basis (appears gross); this project deliberately separates gross sales, discounts, tax, and net sales as distinct measures.
