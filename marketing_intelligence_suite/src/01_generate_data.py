"""
01_generate_data.py
Generates a realistic synthetic marketing-campaign interaction dataset.

Grain of the raw table: one row = one customer exposed to one campaign
(campaign x customer "touch"). Campaign-level budget is allocated to rows
proportionally to impressions so that SUM(budget) at campaign level equals the
planned campaign budget.

Built-in realism:
  * channel-specific CTR / CVR / AOV
  * seasonality (Q4 peak, summer dip, monthly noise)
  * diminishing returns: conversions ~ budget ** 0.65
  * segment / age / device / region effects
  * customer-level latent "propensity" that drives repeat purchases (for RFM / churn / CLV)
"""
import numpy as np
import pandas as pd
from pathlib import Path

RNG = np.random.default_rng(42)
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)

N_CAMPAIGNS = 120
N_CUSTOMERS = 2200
TARGET_ROWS = 6500
START, END = pd.Timestamp("2024-01-01"), pd.Timestamp("2025-12-31")

# --------------------------------------------------------------------------- #
# Channel economics (per-impression behaviour)
# --------------------------------------------------------------------------- #
CHANNELS = {
    #            share  CPM(EUR)  CTR    CVR(click->conv)  AOV   brand_lift
    #            share  cost per reached customer(EUR)  CTR    CVR(click->conv)  AOV
    "search":  dict(share=0.28, cpt=9.0, ctr=0.11, cvr=0.34, aov=210),
    "email":   dict(share=0.22, cpt=2.4, ctr=0.075, cvr=0.30, aov=165),
    "social":  dict(share=0.24, cpt=5.5, ctr=0.045, cvr=0.20, aov=140),
    "display": dict(share=0.16, cpt=5.2, ctr=0.014, cvr=0.14, aov=120),
    "tv":      dict(share=0.10, cpt=13.0, ctr=0.006, cvr=0.18, aov=260),
}
REGIONS = {"Bratislava": 0.30, "Western Slovakia": 0.22, "Central Slovakia": 0.20,
           "Eastern Slovakia": 0.18, "Czech Republic": 0.10}
SEGMENTS = {"New": 0.30, "Regular": 0.38, "Loyal": 0.20, "At-Risk": 0.12}
SEG_CVR_MULT = {"New": 0.75, "Regular": 1.0, "Loyal": 1.55, "At-Risk": 0.55}
SEG_AOV_MULT = {"New": 0.85, "Regular": 1.0, "Loyal": 1.35, "At-Risk": 0.9}
DEVICES = {"mobile": 0.58, "desktop": 0.34, "tablet": 0.08}
DEV_CVR_MULT = {"mobile": 0.85, "desktop": 1.25, "tablet": 1.0}
REGION_AOV_MULT = {"Bratislava": 1.15, "Western Slovakia": 1.0, "Central Slovakia": 0.95,
                   "Eastern Slovakia": 0.9, "Czech Republic": 1.05}


def seasonality(ts: pd.Timestamp) -> float:
    """Multiplicative seasonal index for conversion propensity."""
    m = ts.month
    base = {1: 0.85, 2: 0.88, 3: 0.95, 4: 1.0, 5: 1.02, 6: 0.90,
            7: 0.78, 8: 0.76, 9: 1.0, 10: 1.10, 11: 1.45, 12: 1.35}[m]
    return base


# --------------------------------------------------------------------------- #
# Customers
# --------------------------------------------------------------------------- #
cust = pd.DataFrame({
    "customer_id": [f"C{str(i).zfill(5)}" for i in range(1, N_CUSTOMERS + 1)],
    "customer_age": np.clip(RNG.normal(38, 12, N_CUSTOMERS).round(), 18, 75).astype(int),
    "customer_segment": RNG.choice(list(SEGMENTS), N_CUSTOMERS, p=list(SEGMENTS.values())),
    "region": RNG.choice(list(REGIONS), N_CUSTOMERS, p=list(REGIONS.values())),
    "preferred_device": RNG.choice(list(DEVICES), N_CUSTOMERS, p=list(DEVICES.values())),
    "tenure_months": RNG.integers(1, 72, N_CUSTOMERS),
})
# latent propensity (drives repeat behaviour, churn and CLV)
cust["propensity"] = np.clip(
    RNG.beta(2, 5, N_CUSTOMERS)
    + cust["customer_segment"].map({"New": -0.05, "Regular": 0.0, "Loyal": 0.18, "At-Risk": -0.12})
    + (cust["tenure_months"] / 72) * 0.10, 0.02, 0.95)
# observable behavioural attributes correlated with latent propensity (available to the models)
cust["loyalty_member"] = (RNG.random(N_CUSTOMERS) < cust["propensity"] * 0.9).astype(int)
cust["email_opt_in"] = (RNG.random(N_CUSTOMERS) < 0.35 + cust["propensity"] * 0.6).astype(int)
cust["past_purchases_12m"] = RNG.poisson(7 * cust["propensity"] ** 1.3)
cust["app_sessions_30d"] = np.round(RNG.gamma(2, 6 * cust["propensity"] + 0.5)).astype(int)
# age effect: 30-50 convert best
cust["age_factor"] = 1 - (np.abs(cust["customer_age"] - 38) / 45)

# --------------------------------------------------------------------------- #
# Campaigns
# --------------------------------------------------------------------------- #
chan_list = RNG.choice(list(CHANNELS), N_CAMPAIGNS, p=[c["share"] for c in CHANNELS.values()])
# 5 campaigns launched every month (stratified) so that every month is covered
month_starts = pd.date_range(START, END, freq="MS")
starts = pd.to_datetime([ms + pd.Timedelta(days=int(d)) for ms in month_starts
                         for d in RNG.integers(0, 27, N_CAMPAIGNS // len(month_starts))])
starts = pd.DatetimeIndex(RNG.permutation(starts.values))
durations = RNG.integers(7, 45, N_CAMPAIGNS)
# intensity = how much is spent per reached customer relative to channel norm (drives diminishing returns)
intensity = np.exp(RNG.normal(0, 0.45, N_CAMPAIGNS))
reach_plan = np.exp(RNG.normal(np.log(50), 0.55, N_CAMPAIGNS))  # planned reached customers in sample

objectives = RNG.choice(["Acquisition", "Retention", "Cross-sell", "Brand"], N_CAMPAIGNS,
                        p=[0.40, 0.25, 0.20, 0.15])
camp = pd.DataFrame({
    "campaign_id": [f"CMP-{str(i).zfill(3)}" for i in range(1, N_CAMPAIGNS + 1)],
    "campaign_name": [f"{o} {c.title()} {s.strftime('%b%y')}" for o, c, s in zip(objectives, chan_list, starts)],
    "objective": objectives,
    "channel": chan_list,
    "start_date": starts,
    "duration_days": durations,
    "intensity": intensity,
    "reach_plan": reach_plan,
})
camp["budget"] = np.round(camp["reach_plan"] * camp["intensity"]
                          * camp["channel"].map({k: v["cpt"] for k, v in CHANNELS.items()}) , -1)
camp["end_date"] = (camp["start_date"] + pd.to_timedelta(camp["duration_days"], unit="D")).clip(upper=END)

# Rows per campaign proportional to budget^0.65 (diminishing reach), TV low-touch
weights = camp["reach_plan"]
rows_per_camp = np.maximum(12, np.round(weights / weights.sum() * TARGET_ROWS)).astype(int)

# --------------------------------------------------------------------------- #
# Interactions
# --------------------------------------------------------------------------- #
records = []
for (_, c), n in zip(camp.iterrows(), rows_per_camp):
    ch = CHANNELS[c["channel"]]
    # Retention / Cross-sell campaigns target existing (higher-propensity) customers
    if c["objective"] in ("Retention", "Cross-sell"):
        p = (cust["propensity"] ** 1.5).to_numpy()
    else:
        p = np.ones(N_CUSTOMERS)
    idx = RNG.choice(N_CUSTOMERS, size=n, replace=False, p=p / p.sum())
    cs = cust.iloc[idx]

    touch_dates = c["start_date"] + pd.to_timedelta(RNG.integers(0, c["duration_days"], n), unit="D")
    touch_dates = pd.DatetimeIndex(np.minimum(touch_dates.values, END.to_datetime64()))
    season = np.array([seasonality(d) for d in touch_dates])

    # Impressions per touch: frequency grows with budget but with diminishing returns
    lam = {"search": 3, "email": 2.2, "social": 6, "display": 12, "tv": 9}[c["channel"]] * c["intensity"] ** 0.8
    impressions = RNG.poisson(lam, n) + 1

    device = np.where(RNG.random(n) < 0.75, cs["preferred_device"].to_numpy(),
                      RNG.choice(list(DEVICES), n, p=list(DEVICES.values())))

    # diminishing returns: more spend per customer -> more impressions but lower effectiveness per impression
    dim_ret = c["intensity"] ** -0.12

    ctr = ch["ctr"] * (0.8 + 0.4 * cs["age_factor"].to_numpy()) * np.where(device == "desktop", 1.1, 1.0) * dim_ret
    clicks = RNG.binomial(impressions, np.clip(ctr, 0, 0.6))

    cvr = (ch["cvr"] * cs["customer_segment"].map(SEG_CVR_MULT).to_numpy()
           * np.vectorize(DEV_CVR_MULT.get)(device) * season * (0.7 + 0.6 * cs["age_factor"].to_numpy())
           * (0.25 + 1.5 * cs["propensity"].to_numpy()) * dim_ret)
    # TV: brand conversions occur without measurable click
    if c["channel"] == "tv":
        conv_trials = np.maximum(clicks, RNG.binomial(impressions, 0.08))
    else:
        conv_trials = clicks
    conversions = RNG.binomial(conv_trials, np.clip(cvr, 0, 0.9))
    conversions = np.where(conversions > 2, 2, conversions)  # cap per touch

    aov = (ch["aov"] * cs["customer_segment"].map(SEG_AOV_MULT).to_numpy()
           * cs["region"].map(REGION_AOV_MULT).to_numpy() * np.exp(RNG.normal(0, 0.25, n)))
    revenue = np.round(conversions * aov, 2)

    records.append(pd.DataFrame({
        "campaign_id": c["campaign_id"], "channel": c["channel"],
        "start_date": c["start_date"], "end_date": c["end_date"], "touch_date": touch_dates,
        "customer_id": cs["customer_id"].to_numpy(), "customer_age": cs["customer_age"].to_numpy(),
        "customer_segment": cs["customer_segment"].to_numpy(), "region": cs["region"].to_numpy(),
        "device_type": device, "impressions": impressions, "clicks": clicks,
        "conversions": conversions, "revenue": revenue,
    }))

df = pd.concat(records, ignore_index=True)
# Allocate campaign budget to rows proportional to impressions
imp_share = df["impressions"] / df.groupby("campaign_id")["impressions"].transform("sum")
df["budget"] = (imp_share * df["campaign_id"].map(camp.set_index("campaign_id")["budget"])).round(2)
df["cost"] = df["budget"]  # spend == planned budget (fully delivered campaigns)

cols = ["campaign_id", "channel", "start_date", "end_date", "touch_date", "budget", "impressions", "clicks",
        "conversions", "revenue", "customer_id", "customer_age", "customer_segment", "region", "device_type"]
df = df[cols].sort_values(["start_date", "campaign_id", "touch_date"]).reset_index(drop=True)
df.insert(0, "interaction_id", [f"INT-{i:06d}" for i in range(1, len(df) + 1)])

df.to_csv(OUT / "marketing_interactions.csv", index=False)
camp.drop(columns=["intensity", "reach_plan"]).to_csv(OUT / "campaigns_master.csv", index=False)
cust.drop(columns=["propensity", "age_factor"]).to_csv(OUT / "customers_master.csv", index=False)

print(f"rows={len(df):,}  campaigns={camp.shape[0]}  customers={df.customer_id.nunique():,}")
print(df.groupby("channel")[["impressions", "clicks", "conversions", "revenue", "budget"]].sum()
        .assign(CTR=lambda x: x.clicks / x.impressions, ROAS=lambda x: x.revenue / x.budget).round(3))
