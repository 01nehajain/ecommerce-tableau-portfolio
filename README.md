# E-Commerce Sales & Customer Intelligence — Tableau Portfolio Project

An end-to-end analytics project on 138K+ e-commerce transactions (2021–2025): data cleaning, feature engineering, RFM customer segmentation, and a six-dashboard Tableau workbook design — built to demonstrate the full path from raw transactional data to business decisions, not just chart-making.

> **Headline finding:** the products/categories that generate the *most revenue* are not the ones generating the *most profit* — and the point where discounting stops paying for itself is identifiable in the data (see [Key Findings](#key-findings)).

---

## 1. Repository structure

```
ecommerce-tableau-portfolio/
├── README.md                     <- you are here
├── data/
│   ├── raw/                      <- original source files (as provided)
│   └── processed/                <- cleaned fact tables + pre-aggregated marts (pipeline output)
├── notebooks/
│   └── 01_data_pipeline.py       <- cleaning, feature engineering, RFM, all aggregations
├── tableau/
│   └── dashboard_spec.md         <- worksheet-by-worksheet build spec + calculated field formulas
└── docs/
    └── data_dictionary.md        <- column-level documentation of every processed table
```


---

## 2. Source data

| File | Grain | Rows | Purpose |
|---|---|---|---|
| `ecommerce_sales_customer_analytics_150k.csv` | 1 row = 1 order | 138,116 | Primary fact table: order, customer, payment, delivery, return, marketing, and financial fields |
| `order_items.csv` | 1 row = 1 product line within an order | 397,569 | Line-item detail needed for true product/category/brand analysis |
| `product_catalog.csv` | 1 row = 1 product | 1,175 | Category, sub-category, brand, supplier, cost, list price |
| `customer_master.csv` | 1 row = 1 customer | 25,000 | Demographics, acquisition cost, segment |
| `dataset_statistics.csv` | 1 row | 1 | Publisher-provided summary stats (used to sanity-check the pipeline) |

**Sanity check against publisher stats:** publisher reports 138,116 transactions / $177.1M revenue / 6.85% return rate. My pipeline reproduces order count exactly; minor revenue variance is expected because "Total Revenue" in the publisher file is gross, while this project separates gross sales, discounts, tax, and net sales as distinct measures (a deliberate design choice — see below).

---

## 3. What the pipeline does (`notebooks/01_data_pipeline.py`)

1. **Cleans & types** dates, booleans, and categorical fields.
2. **Engineers features:** year/quarter/month, weekday, discount-% bands, delivery-speed bands, profit-margin flags.
3. **Builds RFM segmentation** (Recency / Frequency / Monetary, quintile-scored) on **completed orders only**, joined back to customer demographics — output: 8 behavioral segments (Champions, Loyal, At Risk, Hibernating, etc.), not just the dataset's pre-labeled Consumer/Premium/VIP/Business tiers.
4. **Builds a true product-level fact table** by joining `order_items` → `product_catalog` → `orders`, since the main file is order-grain and cannot answer "which *product*" questions on its own.
5. **Writes 13 pre-aggregated marts** to `data/processed/` so Tableau extracts stay fast and every dashboard has a purpose-built table instead of hitting the 138K-row fact table with live calculations for every view.


### A data-quality caveat worth stating out loud (and I did, in the code)
`delivery_days`, `estimated_delivery_days`, `customer_rating`, and `delivery_status` are only populated for **Completed** orders — Cancelled, Pending, and Returned orders never reach delivery or get rated. That means "does delivery time predict returns?" **cannot be answered directly from this dataset** (the two fields never co-occur on returned rows). I scoped the delivery/rating analysis to completed orders only and documented this rather than silently joining across a gap. This kind of caveat is exactly what "inspect before analyzing" in the dataset's own usage notes is asking for.

Similarly, `is_repeat_customer` is `True` for 99.8% of rows — it's not a useful segmentation field in this data — so the RFM-derived segments are used instead of relying on it.

---

## 4. Key findings

These are the findings the Tableau workbook is designed to make visible at a glance, computed directly from the data (not the publisher's marketing copy):

**Revenue leaders are not profit leaders.**
Electronics is the #1 category by revenue ($41.1M) but has the *thinnest* margin of any category (34.3%) — nearly the mirror image of Grocery, which is far smaller in revenue ($3.0M) but the *most* profitable category on a margin basis (55.1%). Automotive tells the same story (39.4% margin) despite being the #4 category by revenue.

**Discounting has a cliff, not a slope.**
Profit margin degrades steadily as discount depth increases, then falls off sharply:

| Discount band | Orders | Avg. profit margin |
|---|---:|---:|
| No discount | 17,864 | 54.1% |
| 1–10% | 35,031 | 51.1% |
| 11–20% | 49,198 | 46.7% |
| 21–30% | 17,729 | 40.3% |
| 31–40% | 10,882 | 31.4% |
| 41%+ | 7,412 | **15.7%** |

The 21%→41%+ range is where discounting stops being a growth lever and starts being a margin problem — margin more than halves (40.3% → 15.7%) for a discount band that represents only a modest further increase in headline discount depth.

**Delivery speed measurably affects the customer experience — where it can be measured.**
Among completed orders, average rating drops from **4.02 (Early)** → **3.73 (On Time)** → **3.22 (Delayed)**. This is a clean, decision-usable signal that operational performance (not just product quality) drives satisfaction — but as noted above, its relationship to *returns* can't be tested directly with this dataset's structure.

**RFM segmentation reveals value hiding under the surface labels.**
Using behavior-based RFM segments (rather than the dataset's built-in Consumer/Premium/VIP/Business labels, which show almost no differentiation in return rate or repeat rate), **Champions + Loyal Customers together generate ~43% of total monetary value** from a minority of the customer base, while a "Cannot Lose Them" segment — high historical value but gone quiet — is small in count but represents real revenue at risk.

**Return reasons are evenly spread, not dominated by one root cause.**
The eight return reasons are within a narrow band of each other (1,138–1,237 orders each) — there is no single dominant failure mode, which itself is a finding: a fix targeted at one reason (e.g. sizing) would only address ~13% of return volume.

**Regional performance is closer than it looks at the revenue level.**
South leads on raw order volume and revenue (largest customer base), but North has the highest profit margin (46.1%) and second-highest AOV ($1,357) despite being the smallest region by volume — a classic "small but efficient" market worth flagging in the executive dashboard rather than letting volume dominate the story.

---

## 5. Tableau dashboard plan

Full worksheet-by-worksheet spec, chart types, filters, and calculated-field formulas are in **[`tableau/dashboard_spec.md`](tableau/dashboard_spec.md)**. Summary of the six dashboards:

1. **Executive Overview** — KPI scorecards (revenue, profit, orders, AOV, margin) + monthly trend + region map
2. **Sales & Profitability** — revenue-vs-profit category quadrant, brand leaderboard, the discount-cliff chart above
3. **Customer Intelligence** — RFM segment treemap, segment-value bar chart, demographics breakdown
4. **Product Performance** — category/sub-category drill-down, top/bottom products by margin
5. **Marketing Channel Performance** — channel comparison on revenue-per-customer (not just order count)
6. **Logistics & Returns** — delivery-speed vs rating, return-reason Pareto, return rate by category

Data source for each dashboard = one of the pre-built marts in `data/processed/`, so no dashboard forces Tableau to aggregate the full 138K/397K-row fact tables live.

---



## Tools used

Python (pandas, numpy) for the pipeline · Tableau for visualization · designed to also work in Power BI or a SQL warehouse with minimal changes, since every mart is a plain flat table.
