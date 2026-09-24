"""
04_export_star_schema.py
Builds a Power BI / Qlik-ready star schema and exports CSV + a single Excel workbook.

  fact_campaign_interactions  (grain: campaign x customer touch)   -> FK: campaign_id, customer_id, channel_id, date_key
  fact_campaigns              (grain: campaign, pre-aggregated KPIs) -> FK: campaign_id, channel_id, start_date_key
  dim_campaigns, dim_customers (with RFM segment + churn score), dim_channels, dim_dates, dim_segments
  measures_dax.txt            copy-paste DAX measure definitions
"""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "powerbi"
OUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(ROOT / "data/raw/marketing_interactions.csv", parse_dates=["start_date", "end_date", "touch_date"])
camp = pd.read_csv(ROOT / "data/raw/campaigns_master.csv", parse_dates=["start_date", "end_date"])
cust = pd.read_csv(ROOT / "data/raw/customers_master.csv")
rfm = pd.read_csv(ROOT / "data/raw/customer_rfm_segments.csv")
churn = pd.read_csv(ROOT / "outputs/models/churn_scores.csv", index_col=0)[["churn_probability"]]

# ---- dim_channels
dim_channels = pd.DataFrame({
    "channel_id": [1, 2, 3, 4, 5],
    "channel": ["search", "email", "social", "display", "tv"],
    "channel_name": ["Paid Search", "Email / CRM", "Paid Social", "Programmatic Display", "TV"],
    "channel_type": ["Digital", "Owned", "Digital", "Digital", "Offline"],
    "funnel_stage": ["Lower", "Retention", "Mid", "Upper", "Upper"],
})

# ---- dim_dates (covers all touch dates)
dr = pd.date_range(df["touch_date"].min().normalize(), df["touch_date"].max().normalize(), freq="D")
dim_dates = pd.DataFrame({"date": dr})
dim_dates["date_key"] = dim_dates["date"].dt.strftime("%Y%m%d").astype(int)
dim_dates["year"] = dim_dates["date"].dt.year
dim_dates["quarter"] = "Q" + dim_dates["date"].dt.quarter.astype(str)
dim_dates["year_quarter"] = dim_dates["year"].astype(str) + "-" + dim_dates["quarter"]
dim_dates["month_number"] = dim_dates["date"].dt.month
dim_dates["month_name"] = dim_dates["date"].dt.strftime("%b")
dim_dates["year_month"] = dim_dates["date"].dt.strftime("%Y-%m")
dim_dates["week_of_year"] = dim_dates["date"].dt.isocalendar().week.astype(int)
dim_dates["day_of_week"] = dim_dates["date"].dt.day_name()
dim_dates["is_weekend"] = dim_dates["date"].dt.dayofweek.isin([5, 6])
dim_dates["is_peak_season"] = dim_dates["month_number"].isin([11, 12])
dim_dates = dim_dates[["date_key", "date", "year", "quarter", "year_quarter", "month_number", "month_name", "year_month", "week_of_year", "day_of_week", "is_weekend", "is_peak_season"]]

# ---- dim_segments (CRM lifecycle segment lookup)
dim_segments = pd.DataFrame({"customer_segment": ["New", "Regular", "Loyal", "At-Risk"],
                             "segment_order": [1, 2, 3, 4],
                             "segment_description": ["Acquired < 6 months ago", "Active, standard value", "High value, high frequency", "Declining activity, churn risk"]})

# ---- dim_customers
dim_customers = cust.merge(rfm[["customer_id", "recency_days", "frequency", "monetary", "segment_name"]], on="customer_id", how="left") \
                    .merge(churn, left_on="customer_id", right_index=True, how="left")
dim_customers = dim_customers.rename(columns={"segment_name": "rfm_segment", "frequency": "rfm_frequency", "monetary": "rfm_monetary", "recency_days": "rfm_recency_days"})
dim_customers["age_group"] = pd.cut(dim_customers["customer_age"], [17, 25, 35, 45, 55, 100], labels=["18-25", "26-35", "36-45", "46-55", "56+"]).astype(str)
dim_customers["churn_risk_band"] = pd.cut(dim_customers["churn_probability"], [-0.01, 0.6, 0.8, 1.01], labels=["Low", "Medium", "High"]).astype(str).replace("nan", "Not scored")
dim_customers["is_buyer"] = dim_customers["rfm_frequency"].fillna(0) > 0

# ---- dim_campaigns
dim_campaigns = camp.copy()
dim_campaigns["start_date_key"] = dim_campaigns["start_date"].dt.strftime("%Y%m%d").astype(int)
dim_campaigns["end_date_key"] = dim_campaigns["end_date"].dt.strftime("%Y%m%d").astype(int)
dim_campaigns = dim_campaigns.merge(dim_channels[["channel", "channel_id"]], on="channel")
dim_campaigns["budget_band"] = pd.cut(dim_campaigns["budget"], [0, 200, 500, 1000, 1e9], labels=["< €200", "€200-500", "€500-1K", "> €1K"]).astype(str)

# ---- fact_campaign_interactions
fact = df.merge(dim_channels[["channel", "channel_id"]], on="channel")
fact["date_key"] = fact["touch_date"].dt.strftime("%Y%m%d").astype(int)
fact["responded"] = (fact["conversions"] > 0).astype(int)
fact = fact[["interaction_id", "campaign_id", "customer_id", "channel_id", "date_key", "device_type",
             "impressions", "clicks", "conversions", "revenue", "budget", "responded"]].rename(columns={"budget": "spend"})

# ---- fact_campaigns (aggregated, with pre-computed KPI columns for Qlik / quick checks)
fc = df.groupby("campaign_id").agg(impressions=("impressions", "sum"), clicks=("clicks", "sum"), conversions=("conversions", "sum"),
                                   revenue=("revenue", "sum"), spend=("budget", "sum"), reached_customers=("customer_id", "nunique"),
                                   responders=("conversions", lambda s: (s > 0).sum())).reset_index()
fc = fc.merge(dim_campaigns[["campaign_id", "channel_id", "objective", "start_date_key", "duration_days", "budget"]], on="campaign_id")
fc["CTR"] = fc["clicks"] / fc["impressions"]
fc["CVR"] = np.where(fc["clicks"] > 0, fc["conversions"] / fc["clicks"], np.nan)
fc["response_rate"] = fc["responders"] / fc["reached_customers"]
fc["CPC"] = np.where(fc["clicks"] > 0, fc["spend"] / fc["clicks"], np.nan)
fc["CAC"] = np.where(fc["conversions"] > 0, fc["spend"] / fc["conversions"], np.nan)
fc["ROAS"] = fc["revenue"] / fc["spend"]
fc["profit"] = fc["revenue"] - fc["spend"]
fc["spend_per_customer"] = fc["spend"] / fc["reached_customers"]

tables = {"fact_campaign_interactions": fact, "fact_campaigns": fc, "dim_campaigns": dim_campaigns, "dim_customers": dim_customers,
          "dim_channels": dim_channels, "dim_dates": dim_dates, "dim_segments": dim_segments}
for n, t in tables.items():
    t.to_csv(OUT / f"{n}.csv", index=False)
with pd.ExcelWriter(OUT / "marketing_star_schema.xlsx", engine="openpyxl") as xw:
    for n, t in tables.items():
        t.to_excel(xw, sheet_name=n[:31], index=False)

DAX = """
// ============ Power BI measures (create in table: fact_campaign_interactions) ============
Total Spend        = SUM ( fact_campaign_interactions[spend] )
Total Revenue      = SUM ( fact_campaign_interactions[revenue] )
Total Impressions  = SUM ( fact_campaign_interactions[impressions] )
Total Clicks       = SUM ( fact_campaign_interactions[clicks] )
Total Conversions  = SUM ( fact_campaign_interactions[conversions] )
Reached Customers  = DISTINCTCOUNT ( fact_campaign_interactions[customer_id] )
Responders         = CALCULATE ( DISTINCTCOUNT ( fact_campaign_interactions[customer_id] ), fact_campaign_interactions[responded] = 1 )

CTR                = DIVIDE ( [Total Clicks], [Total Impressions] )
CVR                = DIVIDE ( [Total Conversions], [Total Clicks] )
Response Rate      = DIVIDE ( [Responders], [Reached Customers] )
CPC                = DIVIDE ( [Total Spend], [Total Clicks] )
CAC                = DIVIDE ( [Total Spend], [Total Conversions] )
ROAS               = DIVIDE ( [Total Revenue], [Total Spend] )
AOV                = DIVIDE ( [Total Revenue], [Total Conversions] )
Profit             = [Total Revenue] - [Total Spend]
Spend Share        = DIVIDE ( [Total Spend], CALCULATE ( [Total Spend], ALL ( dim_channels ) ) )
Revenue Share      = DIVIDE ( [Total Revenue], CALCULATE ( [Total Revenue], ALL ( dim_channels ) ) )
Share Gap (pp)     = ( [Revenue Share] - [Spend Share] ) * 100

// ---- time intelligence (requires dim_dates marked as date table)
Revenue PY         = CALCULATE ( [Total Revenue], SAMEPERIODLASTYEAR ( dim_dates[date] ) )
Revenue YoY %      = DIVIDE ( [Total Revenue] - [Revenue PY], [Revenue PY] )
Revenue MTD        = TOTALMTD ( [Total Revenue], dim_dates[date] )
Rolling 3M Revenue = CALCULATE ( [Total Revenue], DATESINPERIOD ( dim_dates[date], MAX ( dim_dates[date] ), -3, MONTH ) )

// ---- KPI status for conditional formatting
ROAS Status        = SWITCH ( TRUE (), [ROAS] >= 3, "Strong", [ROAS] >= 1, "Break-even+", "Loss" )
ROAS Target        = 2.5
ROAS vs Target     = [ROAS] - [ROAS Target]

// ---- customer intelligence (dim_customers)
High Churn Risk Customers = CALCULATE ( COUNTROWS ( dim_customers ), dim_customers[churn_risk_band] = "High" )
Champions Revenue         = CALCULATE ( [Total Revenue], dim_customers[rfm_segment] = "Champions" )
Avg Churn Probability     = AVERAGE ( dim_customers[churn_probability] )
"""
(OUT / "measures_dax.txt").write_text(DAX.strip())

QLIK = """
// ============ Qlik Sense master measures ============
CTR            : Sum(clicks) / Sum(impressions)
CVR            : Sum(conversions) / Sum(clicks)
Response Rate  : Count(DISTINCT {<responded={1}>} customer_id) / Count(DISTINCT customer_id)
CPC            : Sum(spend) / Sum(clicks)
CAC            : Sum(spend) / Sum(conversions)
ROAS           : Sum(revenue) / Sum(spend)
AOV            : Sum(revenue) / Sum(conversions)
Profit         : Sum(revenue) - Sum(spend)
Revenue YoY %  : (Sum(revenue) - Sum({<year={"$(=Max(year)-1)"}>} revenue)) / Sum({<year={"$(=Max(year)-1)"}>} revenue)
"""
(OUT / "measures_qlik.txt").write_text(QLIK.strip())

print({n: t.shape for n, t in tables.items()})
