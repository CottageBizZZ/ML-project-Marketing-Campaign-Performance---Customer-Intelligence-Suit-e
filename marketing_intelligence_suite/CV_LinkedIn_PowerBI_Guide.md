# Marketing Campaign Performance & Customer Intelligence Suite — CV materials & Power BI guide

Все цифры ниже взяты из фактических результатов пайплайна (`outputs/facts_payload.json`, `outputs/models/model_results.json`).

---

## 1. Bullet points для CV (раздел Projects)

**Marketing Campaign Performance & Customer Intelligence Suite** | Python, SQL-ready star schema, Power BI, scikit-learn, XGBoost, SHAP | [GitHub link]

- Built an end-to-end marketing analytics pipeline (Python → star-schema export → Power BI) over 6.5K campaign-customer touches, 120 campaigns and 5 channels, computing CTR, CVR, CPC, CAC, ROAS and response-rate KPIs by channel, segment, region, device and month.
- Identified a budget misallocation worth ~€8K of annual spend: Email delivered 6.5x ROAS and €31 CAC on only 6% of budget while Display ran below break-even (0.84x ROAS, €159 CAC); recommended a 10–15% reallocation with an estimated +15–20% revenue uplift at constant budget.
- Quantified diminishing returns with a fixed-effects log-log model (elasticity −0.71: doubling spend per customer cuts ROAS by ~39%) and Q4 seasonality (Nov–Dec revenue 1.4x an average month), translating both into budget-phasing rules.
- Segmented 566 buyers with RFM + K-means into 4 actionable groups, isolating a "Champions" cohort (9% of buyers, 24% of revenue, avg €950) and 379 one-off lapsed buyers targeted for a win-back journey.
- Trained and compared Logistic Regression, Random Forest and XGBoost response-propensity models (hold-out ROC-AUC 0.75, 3.2x top-decile lift); showed that contacting the top 30% of scored customers captures 62% of all responders, and explained drivers with SHAP.
- Built a 12-month churn model (CV AUC 0.68) revealing 76% of prior-year buyers did not repurchase; delivered churn-risk bands into the customer dimension for dashboard use.
- Designed a Power BI-ready star schema (2 fact + 5 dimension tables, 25 DAX measures incl. time intelligence) and an AI-insight layer that auto-generates a 5-paragraph executive summary strictly from validated KPIs (optional LLM mode).
- Delivered a 12-page stakeholder PDF report (executive summary → methodology → KPI dashboard → segmentation → predictive models → recommendations).

*Короткая версия (3 буллета), если места мало:*

- Designed an end-to-end marketing analytics pipeline (Python → star schema → Power BI) over 6.5K campaign records and 120 campaigns; built KPI framework (CTR, CAC, ROAS, response rate) and uncovered a channel misallocation: Email 6.5x ROAS on 6% of spend vs. Display below break-even.
- Built RFM/K-means segmentation and Random Forest response model (ROC-AUC 0.75, 3.2x top-decile lift) — top 30% of scored customers capture 62% of responders; explained drivers with SHAP.
- Automated an AI executive-summary layer and a 12-page stakeholder report; delivered DAX-ready data model with 25 measures for Power BI/Qlik dashboards.

---

## 2. Описание проекта для cover letter / LinkedIn

**Cover letter (EN):**
To close the gap between my banking analytics experience and marketing analytics, I built the Marketing Campaign Performance & Customer Intelligence Suite: an end-to-end project that turns 120 campaigns' worth of channel, spend and CRM data into a Power BI star schema with 25 DAX measures, an RFM segmentation, response and churn models (ROC-AUC 0.75 / 0.68, SHAP-explained) and an AI-generated executive summary. The analysis surfaced concrete, quantified decisions — a channel reallocation worth +15–20% revenue, spend-intensity caps derived from a −0.71 ROAS elasticity, and a propensity-based targeting rule that reaches 62% of responders with 30% of contacts — which is exactly the kind of "tell the story with data" work this internship describes.

**LinkedIn post / project description (EN):**
Marketing Campaign Performance & Customer Intelligence Suite — an end-to-end analytics portfolio project: Python KPI pipeline (CTR, CAC, ROAS, response rate), RFM + K-means segmentation, Random Forest/XGBoost response model (AUC 0.75, 3.2x lift), churn model with SHAP drivers, Power BI star schema with ready DAX measures, and an AI layer that writes the executive summary from validated numbers. Key finding: Email drove 6.5x ROAS on 6% of budget while Display ran below break-even — a 10–15% reallocation worth an estimated +15–20% revenue.

---

## 3. Power BI: интерактивный дашборд за 30–60 минут

### Шаг 0 — файлы (папка `data/powerbi/`)
`fact_campaign_interactions.csv`, `fact_campaigns.csv`, `dim_campaigns.csv`, `dim_customers.csv`, `dim_channels.csv`, `dim_dates.csv`, `dim_segments.csv`, `measures_dax.txt` (все меры готовы к копированию). Альтернатива — один файл `marketing_star_schema.xlsx` (каждая таблица на своём листе).

### Шаг 1 — загрузка и модель (10 мин)
1. Get Data → Text/CSV (или Excel) → загрузить все 7 таблиц. В Power Query проверить типы: `date` → Date, `date_key`/`start_date_key` → Whole Number, `spend`/`revenue` → Decimal.
2. Model view — связи (все Many-to-One, single direction, к dimension-таблицам):
   - `fact_campaign_interactions[campaign_id]` → `dim_campaigns[campaign_id]`
   - `fact_campaign_interactions[customer_id]` → `dim_customers[customer_id]`
   - `fact_campaign_interactions[channel_id]` → `dim_channels[channel_id]`
   - `fact_campaign_interactions[date_key]` → `dim_dates[date_key]`
   - `fact_campaigns[campaign_id]` → `dim_campaigns[campaign_id]`; `fact_campaigns[channel_id]` → `dim_channels[channel_id]`; `fact_campaigns[start_date_key]` → `dim_dates[date_key]` (inactive, для анализа по дате запуска)
   - `dim_customers[customer_segment]` → `dim_segments[customer_segment]`
3. `dim_dates` → Mark as date table (столбец `date`). Скрыть ключевые столбцы (`*_id`, `*_key`) из report view.

### Шаг 2 — меры (5 мин)
Открыть `measures_dax.txt`, создать пустую таблицу `_Measures` (Enter Data) и добавить меры копированием: Total Spend, Total Revenue, Total Conversions, Reached Customers, Responders, CTR, CVR, Response Rate, CPC, CAC, ROAS, AOV, Profit, Spend Share, Revenue Share, Share Gap (pp), Revenue PY, Revenue YoY %, Rolling 3M Revenue, ROAS Status, ROAS Target, ROAS vs Target, High Churn Risk Customers, Champions Revenue, Avg Churn Probability. Формат: ROAS — `0.0"x"`, проценты — `0.0%`, деньги — `€#,##0`.

### Шаг 3 — страницы и визуалы (25–35 мин)

**Страница 1 — Executive Overview**
- 6 Card visuals: Total Spend, Total Revenue, ROAS, CAC, Response Rate, Reached Customers. Условное форматирование ROAS по мере `ROAS Status`.
- Clustered column chart: ось `dim_channels[channel_name]`, значения `Spend Share`, `Revenue Share` (история про misallocation).
- Line chart: ось `dim_dates[date]` (иерархия Year → Month), значения Total Revenue и Total Spend; добавить `Revenue PY` пунктиром.
- Bar chart (horizontal): `channel_name` × `ROAS`, constant line = 1 (break-even) и `ROAS Target` = 2.5.
- Slicers: Year (`dim_dates[year]`), Channel, Objective (`dim_campaigns[objective]`), Region (`dim_customers[region]`).

**Страница 2 — Campaign Deep-Dive**
- Table/Matrix: `dim_campaigns[campaign_name]`, objective, channel, Total Spend, Total Conversions, CAC, ROAS, Profit; conditional formatting (data bars на ROAS, красный фон при ROAS < 1).
- Scatter chart (diminishing returns): X = `fact_campaigns[spend_per_customer]`, Y = `fact_campaigns[ROAS]`, размер = `spend`, легенда = channel; включить log-scale по X, добавить trend line из Analytics pane.
- Matrix heatmap: строки objective, столбцы channel_name, значение ROAS, conditional formatting (background color scale, центр = 1).
- Decomposition tree: analyze `Total Conversions` by channel → segment → device → region (эффектно на демо).

**Страница 3 — Customer Intelligence**
- Bar chart: `dim_customers[rfm_segment]` × Total Revenue и Reached Customers (или два визуала).
- Matrix: `dim_segments[customer_segment]` × `device_type` → Response Rate (heatmap conditional formatting).
- Column chart: `dim_customers[age_group]` × Response Rate.
- Donut/bar: `dim_customers[churn_risk_band]` × count customers; card `High Churn Risk Customers`.
- Table: топ-50 клиентов по `churn_probability` с rfm_segment, rfm_monetary — «список для win-back кампании».
- Slicers: rfm_segment, churn_risk_band, loyalty_member.

**Страница 4 — Insights (текст)**
- Text box с 5 инсайтами из `outputs/insights.json` / executive summary + Smart Narrative visual (Power BI сам генерирует текст по данным — хорошо сочетается с историей про AI-insight layer).

### Шаг 4 — финиш (5 мин)
- Единая тема: Format → Themes → Customize (основной #20808D, акцент #A84B2F, тёмный #1B474D).
- Включить Drill-through со страницы 1 на страницу 2 по `campaign_name`.
- Bookmarks: «Channel view» / «Customer view». Опубликовать в Power BI Service или сохранить .pbix и добавить 2–3 скриншота в README на GitHub.

### Qlik Sense (если попросят)
Загрузить те же CSV через Data manager (связи подхватятся по одинаковым именам ключей), master measures — из `measures_qlik.txt`.
