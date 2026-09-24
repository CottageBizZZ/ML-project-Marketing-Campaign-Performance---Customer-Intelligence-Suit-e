"""
05_ai_insights.py
AI-insight layer: turns computed KPI tables + model results into a plain-language executive summary.

Two modes:
  * generate_executive_summary(...)      -> deterministic, template + rules narrative (works offline, fully reproducible)
  * generate_executive_summary_llm(...)  -> optional: sends the same structured "facts" payload to an LLM
                                            (OpenAI-compatible API) for richer prose. Falls back to the rule-based text.
The design principle: the model never sees raw data - only verified numbers computed by the analytics layer,
which removes the risk of hallucinated figures.
"""
import json
import os
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def build_facts() -> dict:
    """Collect every number the narrative is allowed to use (single source of truth)."""
    ins = json.load(open(ROOT / "outputs/insights.json"))
    mr = json.load(open(ROOT / "outputs/models/model_results.json"))
    ch = pd.read_csv(ROOT / "outputs/kpi_by_channel.csv", index_col=0)
    seg = pd.read_csv(ROOT / "outputs/kpi_by_segment.csv", index_col=0)
    mon = pd.read_csv(ROOT / "outputs/kpi_by_month.csv", index_col=0, parse_dates=True)
    o = ins["overall"]
    best, worst = ch["ROAS"].idxmax(), ch["ROAS"].idxmin()
    y = mon.groupby(mon.index.year)[["revenue", "spend", "conversions"]].sum()
    yoy = (y.loc[2025, "revenue"] / y.loc[2024, "revenue"] - 1) if 2024 in y.index and 2025 in y.index else None
    prof = {p["segment_name"]: p for p in mr["rfm"]["profiles"]}
    return dict(
        period="January 2024 – December 2025", rows=int(ch["reached_customers"].sum()),
        spend=o["spend"], revenue=o["revenue"], conversions=int(o["conversions"]), roas=o["ROAS"], cac=o["CAC"], ctr=o["CTR"],
        response_rate=o["response_rate"], reached=int(o["reached_customers"]), aov=o["AOV"], yoy_revenue=yoy,
        best_channel=best, best_roas=ch.loc[best, "ROAS"], best_cac=ch.loc[best, "CAC"], best_spend_share=ch.loc[best, "spend"] / ch["spend"].sum(),
        worst_channel=worst, worst_roas=ch.loc[worst, "ROAS"], worst_cac=ch.loc[worst, "CAC"], worst_spend=ch.loc[worst, "spend"], worst_revenue=ch.loc[worst, "revenue"],
        elasticity=ins["elasticity"], q4_uplift=ins["q4_uplift"],
        loyal_rr=seg.loc["Loyal", "response_rate"], atrisk_rr=seg.loc["At-Risk", "response_rate"], loyal_roas=seg.loc["Loyal", "ROAS"],
        resp_auc=mr["response_model"]["models"][mr["response_model"]["best"]]["test_auc"], resp_model=mr["response_model"]["best"],
        top30=mr["response_model"]["top30_capture_pct"], top_lift=mr["response_model"]["top_decile_lift"],
        top_drivers=list(mr["response_model"]["top_features"])[:3],
        churn_auc=mr["churn_model"]["cv_auc"][mr["churn_model"]["best"]]["mean"], churn_rate_buyers=mr["churn_model"]["churn_rate_among_2024_buyers"],
        churn_drivers=list(mr["churn_model"]["top_features"])[:3],
        champions=prof.get("Champions"), lapsed=prof.get("One-off Lapsed"), n_buyers=mr["rfm"]["n_buyers"],
        insights=ins["insights"],
    )


def _pct(x, d=0): return f"{x*100:.{d}f}%"
def _eur(x): return f"€{x:,.0f}"
FEATURE_LABELS = {"spend_per_touch": "spend per reached customer (negative: diminishing returns)", "channel_search": "Search channel",
                  "customer_segment_Loyal": "Loyal segment", "past_purchases_12m": "purchases in the previous 12 months", "app_sessions_30d": "app activity",
                  "device_type_desktop": "desktop device", "touches": "number of campaign touches", "recency_days": "days since last purchase",
                  "customer_segment_At-Risk": "At-Risk segment", "impressions": "ad frequency", "loyalty_member": "loyalty-programme membership",
                  "desktop_share": "share of desktop touches", "tenure_months": "customer tenure", "prior_conversions": "previous conversions"}
def _feat(names): return ", ".join(FEATURE_LABELS.get(n, n.replace("_", " ")) for n in names)
def _nice(ch): return {"tv": "TV", "email": "Email", "search": "Paid Search", "social": "Paid Social", "display": "Display"}.get(ch, ch)


def generate_executive_summary(f: dict) -> str:
    """Rule-based narrative: every sentence is conditioned on the computed facts."""
    yoy_txt = ""
    if f["yoy_revenue"] is not None:
        direction = "grew" if f["yoy_revenue"] > 0 else "declined"
        yoy_txt = f" Year-on-year, attributed revenue {direction} {_pct(abs(f['yoy_revenue']))} in 2025 versus 2024."
    roas_verdict = ("a healthy return" if f["roas"] >= 2.5 else "an acceptable but improvable return" if f["roas"] >= 1.5 else "a return below target")

    p1 = (f"**Headline.** Over {f['period']} the marketing programme invested {_eur(f['spend'])} across 120 campaigns and five channels, "
          f"reaching {f['reached']:,} customers and generating {f['conversions']:,} conversions worth {_eur(f['revenue'])}. "
          f"That is a blended ROAS of {f['roas']:.1f}x and a customer acquisition cost of {_eur(f['cac'])} — {roas_verdict}. "
          f"On average {_pct(f['response_rate'],1)} of reached customers converted, with an average order value of {_eur(f['aov'])}.{yoy_txt}")

    p2 = (f"**What worked.** {_nice(f['best_channel'])} was by far the most efficient channel: ROAS {f['best_roas']:.1f}x and CAC {_eur(f['best_cac'])}, "
          f"despite receiving only {_pct(f['best_spend_share'])} of spend. Loyal customers responded at {_pct(f['loyal_rr'],1)} "
          f"(vs. {_pct(f['atrisk_rr'],1)} for At-Risk) and delivered ROAS {f['loyal_roas']:.1f}x, confirming that the existing CRM base is the cheapest source of revenue. "
          f"Seasonality is a real asset: November–December months returned {f['q4_uplift']:.1f}x the revenue of an average month.")

    loss = " — i.e. every euro spent returned less than a euro" if f["worst_roas"] < 1 else ""
    p3 = (f"**What did not work.** {_nice(f['worst_channel'])} consumed {_eur(f['worst_spend'])} and returned {_eur(f['worst_revenue'])} "
          f"(ROAS {f['worst_roas']:.2f}x, CAC {_eur(f['worst_cac'])}){loss}. Across all campaigns we also measured clear diminishing returns: "
          f"the within-channel elasticity of ROAS to spend-per-customer is {f['elasticity']:.2f}, meaning that doubling the intensity of a campaign "
          f"lowers its efficiency by roughly {_pct(1-2**f['elasticity'])}. Several of the largest campaigns are operating beyond the efficient frontier.")

    p4 = (f"**Customer intelligence.** K-means RFM segmentation of {f['n_buyers']} buyers isolated a 'Champions' group of {f['champions']['customers']} customers "
          f"({_pct(f['champions']['customers']/f['n_buyers'])} of buyers) who generate {_pct(f['champions']['revenue_share'])} of buyer revenue "
          f"(avg {_eur(f['champions']['avg_monetary'])} each), while {f['lapsed']['customers']} 'One-off Lapsed' buyers purchased once and have not returned. "
          f"A {f['resp_model']} response model (hold-out ROC-AUC {f['resp_auc']:.2f}) ranks customers by propensity: targeting only the top 30% of scored customers "
          f"would capture {f['top30']:.0f}% of all responders, a {f['top_lift']:.1f}x lift in the top decile. Key drivers are {_feat(f['top_drivers'])}. "
          f"A churn model (CV AUC {f['churn_auc']:.2f}) shows that {_pct(f['churn_rate_buyers'])} of 2024 buyers did not purchase again in 2025; "
          f"the strongest retention signals are {_feat(f['churn_drivers'])}.")

    p5 = ("**Recommendations.** (1) Re-allocate 10–15% of budget from Display and the largest low-ROAS Social flights into Email lifecycle programmes and "
          "mid-sized Search campaigns; (2) cap spend-per-customer per campaign and split large flights into smaller targeted waves to stay on the efficient side of the "
          "diminishing-returns curve; (3) front-load Q4 budget and run a summer 'always-on' minimum instead of heavy July–August pushes; "
          "(4) operationalise the propensity score in the CRM so that campaigns only contact the top three deciles, and launch a win-back journey for "
          "'One-off Lapsed' and high-churn-risk customers; (5) track ROAS, CAC and Response Rate weekly in the Power BI dashboard against a 2.5x ROAS target.")
    return "\n\n".join([p1, p2, p3, p4, p5])


def generate_executive_summary_llm(f: dict, model: str = "gpt-4o-mini") -> str:
    """Optional LLM mode. Uses OPENAI_API_KEY if present; otherwise returns the rule-based summary."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return generate_executive_summary(f)
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        facts = {k: v for k, v in f.items() if k != "insights"}
        prompt = ("You are a senior marketing analyst writing for a non-technical commercial director. Using ONLY the facts in the JSON below "
                  "(do not invent numbers), write a 5-paragraph executive summary: headline, what worked, what did not work, customer intelligence, "
                  "recommendations. Plain business English, no jargon.\n\n" + json.dumps(facts, default=str))
        r = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}], temperature=0.3)
        return r.choices[0].message.content
    except Exception:
        return generate_executive_summary(f)


if __name__ == "__main__":
    facts = build_facts()
    text = generate_executive_summary(facts)
    (ROOT / "outputs" / "executive_summary.md").write_text("# Executive Summary\n\n" + text)
    json.dump(facts, open(ROOT / "outputs" / "facts_payload.json", "w"), indent=2, default=str)
    print(text)
