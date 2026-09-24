"""
02_kpi_eda.py
KPI computation (CTR, CPC, CAC, ROAS, CVR) + EDA charts + insight extraction.
Outputs: outputs/charts/*.png, outputs/kpi_*.csv, outputs/insights.json
"""
import json
import textwrap
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CH = ROOT / "outputs" / "charts"
CH.mkdir(parents=True, exist_ok=True)

plt.style.use("seaborn-v0_8-whitegrid")
plt.rcParams.update({"figure.dpi": 150, "font.size": 11, "axes.titlesize": 14,
                     "axes.titleweight": "bold", "axes.titlelocation": "left"})
TEAL, RUST, DARK, LIGHT, GREY = "#20808D", "#A84B2F", "#1B474D", "#BCE2E7", "#B8BDC2"
LBL = {"search": "Search", "email": "Email", "social": "Social", "display": "Display", "tv": "TV"}
PAL = [TEAL, RUST, DARK, "#FFC553", "#944454", "#848456"]

df = pd.read_csv(ROOT / "data/raw/marketing_interactions.csv", parse_dates=["start_date", "end_date", "touch_date"])
camp = pd.read_csv(ROOT / "data/raw/campaigns_master.csv", parse_dates=["start_date", "end_date"])


def kpis(g: pd.DataFrame) -> pd.Series:
    imp, clk, conv, rev, cost = g["impressions"].sum(), g["clicks"].sum(), g["conversions"].sum(), g["revenue"].sum(), g["budget"].sum()
    return pd.Series({
        "impressions": imp, "clicks": clk, "conversions": conv, "revenue": rev, "spend": cost,
        "CTR": clk / imp if imp else np.nan,
        "CVR": conv / clk if clk else np.nan,                # click -> conversion
        "response_rate": (g["conversions"] > 0).mean(),      # share of reached customers converting
        "CPC": cost / clk if clk else np.nan,
        "CAC": cost / conv if conv else np.nan,
        "ROAS": rev / cost if cost else np.nan,
        "AOV": rev / conv if conv else np.nan,
        "reached_customers": g["customer_id"].nunique(),
    })


overall = kpis(df)
by_channel = df.groupby("channel").apply(kpis).sort_values("ROAS", ascending=False)
by_segment = df.groupby("customer_segment").apply(kpis).sort_values("ROAS", ascending=False)
by_region = df.groupby("region").apply(kpis).sort_values("ROAS", ascending=False)
by_device = df.groupby("device_type").apply(kpis)
df["month"] = df["touch_date"].dt.to_period("M").dt.to_timestamp()
by_month = df.groupby("month").apply(kpis)
by_campaign = df.groupby("campaign_id").apply(kpis).join(camp.set_index("campaign_id")[["channel", "objective", "start_date"]])
by_campaign["spend_per_customer"] = by_campaign["spend"] / by_campaign["reached_customers"]
df["age_group"] = pd.cut(df["customer_age"], [17, 25, 35, 45, 55, 100], labels=["18-25", "26-35", "36-45", "46-55", "56+"])
by_age = df.groupby("age_group", observed=True).apply(kpis)
seg_dev = df.pivot_table(index="customer_segment", columns="device_type", values="conversions",
                         aggfunc=lambda x: (x > 0).mean()) * 100

for name, t in {"overall": overall.to_frame("value"), "channel": by_channel, "segment": by_segment, "region": by_region,
                "device": by_device, "month": by_month, "campaign": by_campaign, "age": by_age}.items():
    t.to_csv(ROOT / "outputs" / f"kpi_by_{name}.csv")

# --------------------------------------------------------------------------- #
# Charts
# --------------------------------------------------------------------------- #
def eur(x, _=None):
    if abs(x) >= 1e4: return f"€{x/1e3:.0f}K"
    return f"€{x/1e3:.1f}K" if abs(x) >= 1e3 else f"€{x:,.0f}"


# 1. Budget share vs revenue share by channel
fig, ax = plt.subplots(figsize=(10, 5.5), layout="constrained")
share = pd.DataFrame({"Spend share": by_channel["spend"] / by_channel["spend"].sum(),
                      "Revenue share": by_channel["revenue"] / by_channel["revenue"].sum()}).sort_values("Revenue share", ascending=False)
x = np.arange(len(share)); w = 0.38
ax.bar(x - w/2, share["Spend share"] * 100, w, color=GREY, label="Share of spend")
ax.bar(x + w/2, share["Revenue share"] * 100, w, color=TEAL, label="Share of revenue")
for i, (s, r) in enumerate(zip(share["Spend share"], share["Revenue share"])):
    ax.text(i - w/2, s*100 + 0.8, f"{s*100:.0f}%", ha="center", fontsize=9, color="#555")
    ax.text(i + w/2, r*100 + 0.8, f"{r*100:.0f}%", ha="center", fontsize=9, color=DARK, fontweight="bold")
ax.set_xticks(x, [LBL[c] for c in share.index])
ax.set_ylabel("% of total")
se_rev = share.loc[["search", "email"], "Revenue share"].sum() * 100; se_sp = share.loc[["search", "email"], "Spend share"].sum() * 100
ax.set_title(f"Budget is misaligned with results: Search & Email generate {se_rev:.0f}% of revenue from {se_sp:.0f}% of spend\n"
             "Share of spend vs share of attributed revenue by channel, Jan 2024 – Dec 2025", fontsize=12)
ax.legend(frameon=False); ax.set_ylim(0, max(share.max()) * 100 + 8)
fig.savefig(CH / "01_spend_vs_revenue_share.png", bbox_inches="tight"); plt.close(fig)

# 2. ROAS and CAC by channel
fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
bc = by_channel.sort_values("ROAS")
colors = [TEAL if v >= 1 else RUST for v in bc["ROAS"]]
axes[0].barh([LBL[c] for c in bc.index], bc["ROAS"], color=colors)
axes[0].axvline(1, color=DARK, ls="--", lw=1); axes[0].text(1.05, -0.45, "break-even", fontsize=8, color=DARK)
for i, v in enumerate(bc["ROAS"]): axes[0].text(v + 0.08, i, f"{v:.1f}x", va="center", fontsize=10)
axes[0].set_title("ROAS by channel\nrevenue / spend", fontsize=12); axes[0].set_xlim(0, bc["ROAS"].max() * 1.2)
bcac = by_channel.sort_values("CAC", ascending=False)
axes[1].barh([LBL[c] for c in bcac.index], bcac["CAC"], color=[RUST if c == "display" else GREY if c != "email" else TEAL for c in bcac.index])
for i, v in enumerate(bcac["CAC"]): axes[1].text(v + 3, i, f"€{v:.0f}", va="center", fontsize=10)
axes[1].set_title("Customer acquisition cost (CAC) by channel\nspend / conversions", fontsize=12)
axes[1].set_xlim(0, bcac["CAC"].max() * 1.2)
fig.savefig(CH / "02_roas_cac_by_channel.png", bbox_inches="tight"); plt.close(fig)

# 3. Monthly trend
fig, ax = plt.subplots(figsize=(12, 4.8), layout="constrained")
m = by_month.copy()
q4_tmp = m[m.index.month.isin([11, 12])]["revenue"].mean() / m[~m.index.month.isin([11, 12])]["revenue"].mean() - 1
ax.plot(m.index, m["revenue"], color=TEAL, lw=2.2, marker="o", ms=4, label="Revenue")
ax.fill_between(m.index, m["revenue"], alpha=0.12, color=TEAL)
ax.plot(m.index, m["spend"], color=RUST, lw=1.8, ls="--", label="Spend")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(eur))
for yr in (2024, 2025):
    ax.axvspan(pd.Timestamp(f"{yr}-11-01"), pd.Timestamp(f"{yr}-12-31"), color="#FFC553", alpha=0.18)
ax.set_ylim(0, m["revenue"].max() * 1.15)
for yr in (2024, 2025):
    ax.text(pd.Timestamp(f"{yr}-11-30"), m["revenue"].max() * 1.08, "Q4", fontsize=9, color="#7a5a00", ha="center", fontweight="bold")
ax.set_title(f"Revenue is seasonal: Nov–Dec months average {q4_tmp:.0%} above the rest of the year\n"
             "Monthly attributed revenue vs media spend", fontsize=12)
ax.legend(frameon=False, loc="upper left"); ax.set_xlabel("")
fig.savefig(CH / "03_monthly_trend.png", bbox_inches="tight"); plt.close(fig)

# 4. Response rate heatmap segment x device
fig, ax = plt.subplots(figsize=(8, 4.5), layout="constrained")
order = ["Loyal", "Regular", "New", "At-Risk"]
sns.heatmap(seg_dev.loc[order, ["desktop", "mobile", "tablet"]], annot=True, fmt=".1f", cmap="Blues", cbar_kws={"label": "response rate, %"}, ax=ax, linewidths=.5)
ax.set_title(f"Loyal customers on desktop respond {seg_dev.loc['Loyal','desktop']/seg_dev.loc['At-Risk','mobile']:.1f}x more often than At-Risk on mobile\nResponse rate (% of reached customers converting) by segment × device", fontsize=12)
ax.set_xlabel(""); ax.set_ylabel("")
fig.savefig(CH / "04_response_heatmap_segment_device.png", bbox_inches="tight"); plt.close(fig)

# 5. Diminishing returns
fig, ax = plt.subplots(figsize=(10, 5.5), layout="constrained")
bcp = by_campaign.dropna(subset=["ROAS"])
for ch, col in zip(["search", "email", "social", "display", "tv"], PAL):
    sub = bcp[bcp["channel"] == ch]
    ax.scatter(sub["spend_per_customer"], sub["ROAS"], s=sub["spend"] / 8 + 15, alpha=0.7, color=col, label=LBL[ch], edgecolor="white", lw=0.5)
# within-channel elasticity: log-log regression with channel fixed effects (demeaned by channel)
lx = np.log(bcp["spend_per_customer"]); ly = np.log(bcp["ROAS"].clip(lower=0.05))
lx_d = lx - lx.groupby(bcp["channel"]).transform("mean"); ly_d = ly - ly.groupby(bcp["channel"]).transform("mean")
b = float(np.polyfit(lx_d, ly_d, 1)[0])
for ch, col in zip(["search", "email", "social", "display", "tv"], PAL):
    sub = bcp[bcp["channel"] == ch]
    grid = np.linspace(sub["spend_per_customer"].min(), sub["spend_per_customer"].max(), 50)
    a_ch = np.log(sub["ROAS"].clip(lower=0.05)).mean() - b * np.log(sub["spend_per_customer"]).mean()
    ax.plot(grid, np.exp(a_ch) * grid ** b, color=col, ls="--", lw=1.2, alpha=0.9)
ax.plot([], [], color=DARK, ls="--", lw=1.2, label=f"within-channel fit, elasticity {b:.2f}")
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel("Spend per reached customer, € (log)"); ax.set_ylabel("Campaign ROAS (log)")
ax.set_title(f"Diminishing returns: doubling spend per customer cuts ROAS by ~{(1-2**b)*100:.0f}%\n"
             "Each bubble = one campaign, size = total spend", fontsize=12)
ax.legend(frameon=False, fontsize=9, ncol=2)
fig.savefig(CH / "05_diminishing_returns.png", bbox_inches="tight"); plt.close(fig)

# 6. Region & age
fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout="constrained")
br = by_region.sort_values("revenue")
axes[0].barh(br.index, br["revenue"], color=[TEAL if i == br["revenue"].idxmax() else GREY for i in br.index])
axes[0].xaxis.set_major_formatter(mticker.FuncFormatter(eur))
for i, (v, r) in enumerate(zip(br["revenue"], br["ROAS"])): axes[0].text(v + 400, i, f"ROAS {r:.1f}x", va="center", fontsize=9)
axes[0].set_title(f"Revenue by region\n{br['revenue'].idxmax()} delivers the largest revenue; {br['ROAS'].idxmax()} the highest ROAS", fontsize=11); axes[0].set_xlim(0, br["revenue"].max() * 1.25)
top_age = by_age["response_rate"].nlargest(2).index.astype(str).tolist()
axes[1].bar(by_age.index.astype(str), by_age["response_rate"] * 100, color=[TEAL if i in top_age else GREY for i in by_age.index.astype(str)])
for i, v in enumerate(by_age["response_rate"] * 100): axes[1].text(i, v + 0.15, f"{v:.1f}%", ha="center", fontsize=9)
axes[1].set_title(f"Response rate by age group\n{' and '.join(sorted(top_age))} are the most responsive groups", fontsize=11); axes[1].set_ylabel("% of reached customers converting")
fig.savefig(CH / "06_region_age.png", bbox_inches="tight"); plt.close(fig)

# 7. Funnel by channel (CTR, CVR)
fig, ax = plt.subplots(figsize=(10, 5), layout="constrained")
f = by_channel.drop(index="tv")[["CTR", "CVR", "response_rate"]].sort_values("response_rate", ascending=False) * 100
x = np.arange(len(f)); w = 0.27
ax.bar(x - w, f["CTR"], w, color=LIGHT, label="CTR (clicks / impressions)")
ax.bar(x, f["CVR"], w, color=TEAL, label="CVR (conversions / clicks)")
ax.bar(x + w, f["response_rate"], w, color=DARK, label="Response rate (converting customers / reached)")
for j, colname in enumerate(["CTR", "CVR", "response_rate"]):
    for i, v in enumerate(f[colname]): ax.text(i + (j - 1) * w, v + 0.4, f"{v:.1f}%", ha="center", fontsize=8)
ax.set_xticks(x, [LBL[c] for c in f.index]); ax.set_ylabel("%")
ax.set_title(f"Funnel efficiency by digital channel: Search converts {f.loc['search','CVR']/10:.0f} of every 10 clicks, Display only {f.loc['display','CVR']/10:.0f}\n"
             "CTR, click-to-conversion rate and customer response rate (TV excluded: offline conversions are not click-attributed)", fontsize=12)
ax.legend(frameon=False, fontsize=9)
fig.savefig(CH / "07_funnel_by_channel.png", bbox_inches="tight"); plt.close(fig)

# 8. Objective x channel ROAS
fig, ax = plt.subplots(figsize=(8, 4.5), layout="constrained")
oc = df.merge(camp[["campaign_id", "objective"]], on="campaign_id").groupby(["objective", "channel"]).apply(lambda g: g.revenue.sum() / g.budget.sum()).unstack()
oc.columns = [LBL[c] for c in oc.columns]
ret_m = oc.loc[["Retention", "Cross-sell"]].mean().mean(); acq_m = oc.loc["Acquisition"].mean()
sns.heatmap(oc, annot=True, fmt=".1f", cmap="RdYlGn", center=1, vmin=0, vmax=6, ax=ax, cbar_kws={"label": "ROAS (capped at 6x)"}, linewidths=.5)
ax.set_title(f"Retention & Cross-sell campaigns average ROAS {ret_m:.1f}x vs {acq_m:.1f}x for Acquisition\nROAS by campaign objective × channel", fontsize=12); ax.set_xlabel(""); ax.set_ylabel("")
fig.savefig(CH / "08_roas_objective_channel.png", bbox_inches="tight"); plt.close(fig)

# --------------------------------------------------------------------------- #
# Insights
# --------------------------------------------------------------------------- #
top = by_channel.index[0]; worst = by_channel.index[-1]
email_share = by_channel.loc["email", "spend"] / by_channel["spend"].sum()
disp = by_channel.loc["display"]
q4 = by_month[by_month.index.month.isin([11, 12])]["revenue"].mean() / by_month[~by_month.index.month.isin([11, 12])]["revenue"].mean()
loyal_rr = by_segment.loc["Loyal", "response_rate"]; atrisk_rr = by_segment.loc["At-Risk", "response_rate"]
desk = by_device.loc["desktop", "response_rate"]; mob = by_device.loc["mobile", "response_rate"]
ret = ret_m; acq = acq_m

insights = [
    dict(id=1, title=f"{top.title()} is the most efficient channel but under-funded",
         text=f"{top.title()} delivers ROAS {by_channel.loc[top,'ROAS']:.1f}x and the lowest CAC (€{by_channel.loc[top,'CAC']:.0f}) "
              f"yet receives only {email_share*100:.0f}% of total spend. Even accounting for its limited reach, shifting a further 10–15% of budget into "
              f"{top} (lifecycle and re-engagement flows) is the highest-ROI reallocation available.", metric="ROAS", value=float(by_channel.loc[top, "ROAS"])),
    dict(id=2, title="Display is the weakest channel" + (" and loses money" if disp["ROAS"] < 1 else ""),
         text=f"Display spend of €{disp['spend']:,.0f} returned €{disp['revenue']:,.0f} (ROAS {disp['ROAS']:.2f}x, CAC €{disp['CAC']:.0f} vs. blended €{overall['CAC']:.0f}). "
              f"CTR is {disp['CTR']*100:.1f}% and click-to-conversion only {disp['CVR']*100:.0f}%. Recommend pausing prospecting display and keeping only retargeting placements.",
         metric="ROAS", value=float(disp["ROAS"])),
    dict(id=3, title=f"Diminishing returns: spend elasticity of ROAS ≈ {b:.2f}",
         text=f"Across 120 campaigns, a 2x increase in spend per reached customer lowers ROAS by ~{(1-2**b)*100:.0f}%. Several large Social and Search campaigns "
              f"are past the efficient frontier; splitting them into smaller, better-targeted flights would recover efficiency.", metric="elasticity", value=float(b)),
    dict(id=4, title=f"Q4 seasonality is worth {q4:.1f}x an average month",
         text=f"November–December revenue averages {q4:.1f}x the rest of the year while spend rises far less. Budget phasing should front-load Q4 and reduce "
              f"July–August activity, where response rates hit the annual low.", metric="q4_uplift", value=float(q4)),
    dict(id=5, title="Loyal customers on desktop are the most responsive audience",
         text=f"Loyal customers respond at {loyal_rr*100:.1f}% vs. {atrisk_rr*100:.1f}% for At-Risk; desktop responds at {desk*100:.1f}% vs. {mob*100:.1f}% on mobile. "
              f"Retention & Cross-sell campaigns average ROAS {ret:.1f}x vs. {acq:.1f}x for Acquisition — the CRM base is the cheapest growth lever.",
         metric="response_rate_gap", value=float(loyal_rr / atrisk_rr)),
]
json.dump(dict(overall=overall.round(4).to_dict(), insights=insights, elasticity=float(b), q4_uplift=float(q4)),
          open(ROOT / "outputs" / "insights.json", "w"), indent=2, default=str)

print(overall.round(3)); print(by_channel.round(3)); print("elasticity", round(b, 3), "q4", round(q4, 2))
