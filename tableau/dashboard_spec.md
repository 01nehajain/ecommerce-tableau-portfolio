# Tableau Build Spec

Connect each dashboard to the mart(s) listed — don't connect worksheets to the raw fact tables (`fact_orders.csv`, `fact_order_items.csv`) unless you need row-level drill-through, since the marts in `data/processed/` are already aggregated for these exact views.

Recommended data source setup in Tableau: add each processed CSV as its own connection (they're already at the right grain), rather than one giant joined extract. Use Tableau's **Data > Extract** on each source for performance.

---

## Dashboard 1 — Executive Overview
**Source:** `agg_monthly_kpis.csv`, `agg_region_performance.csv`

| Worksheet | Chart type | Fields |
|---|---|---|
| KPI scorecards | Text/BAN tiles | SUM(net_sales), SUM(profit), SUM(orders_count), AVG(avg_order_value), profit_margin_pct |
| Revenue & Profit Trend | Dual-axis line | month (continuous) on columns; net_sales + profit on rows |
| Orders vs Returns | Line + bar combo | month; orders_count (bar), return_rate_pct (line, secondary axis) |
| Regional Snapshot | Filled/symbol map | region; color = profit_margin_pct, size = net_sales |

**Calculated fields**
```
// MoM Revenue Growth %
(SUM([net_sales]) - LOOKUP(SUM([net_sales]), -1)) / ABS(LOOKUP(SUM([net_sales]), -1))

// YoY label (if extending monthly mart with year field)
DATENAME('year', [Month])
```

---

## Dashboard 2 — Sales & Profitability
**Source:** `agg_category_performance.csv`, `agg_brand_performance.csv`, `agg_discount_profitability.csv`, `agg_discount_by_category.csv`

| Worksheet | Chart type | Fields |
|---|---|---|
| Revenue vs Profit Quadrant | Scatter plot | X = net_sales, Y = profit_margin_pct, size = units_sold, one mark per product_category, reference lines at median X and median Y to form four quadrants |
| Brand Leaderboard | Horizontal bar, sorted | brand on rows, net_sales on columns, color = profit_margin_pct |
| The Discount Cliff | Dual-axis line/bar | discount_band on columns; net_sales (bar) + avg_profit_margin (line) on rows — **this is the headline chart from the README findings** |
| Discount × Category Heatmap | Highlight table | product_category (rows) × discount_band (columns), color = profit_margin_pct |

**Calculated fields**
```
// Quadrant label for the scatter plot
IF SUM([net_sales]) >= WINDOW_MEDIAN(SUM([net_sales])) AND
   AVG([profit_margin_pct]) >= WINDOW_MEDIAN(AVG([profit_margin_pct]))
THEN "Star (High Rev, High Margin)"
ELSEIF SUM([net_sales]) >= WINDOW_MEDIAN(SUM([net_sales])) AND
       AVG([profit_margin_pct]) < WINDOW_MEDIAN(AVG([profit_margin_pct]))
THEN "Volume Trap (High Rev, Low Margin)"     // <- Electronics lands here
ELSEIF SUM([net_sales]) < WINDOW_MEDIAN(SUM([net_sales])) AND
       AVG([profit_margin_pct]) >= WINDOW_MEDIAN(AVG([profit_margin_pct]))
THEN "Hidden Gem (Low Rev, High Margin)"      // <- Grocery lands here
ELSE "Low Priority (Low Rev, Low Margin)"
END
```

---

## Dashboard 3 — Customer Intelligence
**Source:** `agg_rfm_segment_summary.csv`, `customer_rfm_segments.csv`, `agg_customer_segment_value.csv`

| Worksheet | Chart type | Fields |
|---|---|---|
| RFM Segment Treemap | Treemap | customer_segment_rfm, size = total_monetary, color = avg_recency (reversed, so "redder" = more overdue) |
| Segment Value Bar | Sorted bar | customer_segment_rfm on rows, total_monetary on columns |
| Recency × Frequency Scatter | Scatter, one mark per customer (or binned) | X = recency_days, Y = frequency, color = customer_segment_rfm, size = monetary |
| Declared Segment vs Behavioral Segment | Crosstab / highlight table | customer_segment (Consumer/Premium/VIP/Business) × customer_segment_rfm — makes the point that the declared label and actual behavior segment don't line up 1:1 |
| Demographics | Bar / histogram | customer_age (binned), gender, region |

**Calculated fields**
```
// Value at risk (Champions/Loyal that could slip)
IF [customer_segment_rfm] = "At Risk" OR [customer_segment_rfm] = "Cannot Lose Them (High Value, Inactive)"
THEN [monetary] ELSE 0 END
```

---

## Dashboard 4 — Product Performance
**Source:** `fact_order_items.csv` (only dashboard that benefits from row-level drill; extract and aggregate in Tableau), `agg_category_performance.csv`

| Worksheet | Chart type | Fields |
|---|---|---|
| Category → Sub-category Drilldown | Treemap or hierarchical bar | product_category > product_subcategory, size = net_sales, color = profit_margin_pct |
| Top 10 Products by Revenue | Bar | product_name, net_sales |
| Bottom 10 Products by Margin | Bar | product_name, profit_margin_pct (filter quantity > some minimum to avoid noise from 1-off sales) |
| Rating vs Revenue | Scatter | product_rating (from product_catalog) vs net_sales, one mark per product |

---

## Dashboard 5 — Marketing Channel Performance
**Source:** `agg_marketing_channel.csv`

| Worksheet | Chart type | Fields |
|---|---|---|
| Channel Comparison | Bar, sorted by revenue_per_customer (not orders_count — the point is value, not volume) | marketing_channel, revenue_per_customer |
| Channel Funnel | Bar or bullet | customers, orders_count, net_sales per channel (three-panel small multiple) |
| AOV by Channel | Bar | marketing_channel, aov |

**Calculated fields**
```
// Efficiency index: revenue per customer relative to overall average
SUM([net_sales]) / SUM([customers]) / (TOTAL(SUM([net_sales])) / TOTAL(SUM([customers])))
```

---

## Dashboard 6 — Logistics & Returns
**Source:** `agg_delivery_performance.csv`, `agg_delivery_speed_band.csv`, `agg_return_reasons.csv`, `agg_returns_by_category.csv`

| Worksheet | Chart type | Fields |
|---|---|---|
| Delivery Status vs Rating | Bar | delivery_status (Early/On Time/Delayed), avg_rating — annotate the 4.02 → 3.22 drop |
| Delivery Speed Band vs Rating | Bar | delivery_speed_band, avg_rating |
| Return Reason Pareto | Bar + cumulative % line | return_reason sorted descending by orders_count, cumulative % line overlaid |
| Return Rate by Category | Bar, sorted | product_category, return_rate_pct |

**Note:** include a text annotation on this dashboard referencing the data-quality caveat in the README (delivery/rating fields only exist for completed orders) so a viewer doesn't over-interpret an implied delivery→return link that the data can't support.

---

## General Tableau build notes
- Use a consistent color palette across all six dashboards (e.g. one sequential palette for margin/profit, one categorical palette for regions/channels) — set this once as a custom palette in Tableau's `Preferences.tps` or via workbook color legends.
- Add a global date filter (year/quarter) on Dashboards 1–2 using `month` from `agg_monthly_kpis.csv`, and apply it via a dashboard action to any sheet sharing that field.
- Use dashboard actions (filter + highlight) to let clicking a category in Dashboard 2 filter Dashboard 4's product drilldown.
- Publish to Tableau Public and link the published viz URL back in the main `README.md` once live — that's the single highest-value addition for a portfolio (a live, clickable dashboard beats screenshots).
