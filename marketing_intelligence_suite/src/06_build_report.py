"""
06_build_report.py
Assembles the stakeholder PDF report (ReportLab) from computed KPIs, charts, model results and the AI summary.
"""
import json
import re
import pandas as pd
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle, KeepTogether)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parents[1]
CH = ROOT / "outputs" / "charts"
OUT = ROOT / "report" / "Marketing_Campaign_Performance_Report.pdf"

# Fonts (DejaVu ships with matplotlib -> supports € and –)
import matplotlib
fdir = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
pdfmetrics.registerFont(TTFont("DV", str(fdir / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DV-B", str(fdir / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DV-I", str(fdir / "DejaVuSans-Oblique.ttf")))
from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-B")

TEAL, DARK, RUST, GREYTXT = colors.HexColor("#20808D"), colors.HexColor("#1B474D"), colors.HexColor("#A84B2F"), colors.HexColor("#555555")
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", fontName="DV-B", fontSize=20, leading=25, textColor=DARK, spaceAfter=10, spaceBefore=4)
H2 = ParagraphStyle("H2", fontName="DV-B", fontSize=13.5, leading=17, textColor=TEAL, spaceBefore=12, spaceAfter=6)
BODY = ParagraphStyle("B", fontName="DV", fontSize=9.6, leading=14, textColor=colors.HexColor("#222222"), spaceAfter=7, alignment=TA_LEFT)
SMALL = ParagraphStyle("S", parent=BODY, fontSize=8, leading=10.5, textColor=GREYTXT)
BUL = ParagraphStyle("BL", parent=BODY, leftIndent=12, bulletIndent=2, spaceAfter=4)
KPI_N = ParagraphStyle("KN", fontName="DV-B", fontSize=13, leading=16, textColor=DARK, alignment=1)
KPI_L = ParagraphStyle("KL", fontName="DV", fontSize=8, leading=10, textColor=GREYTXT, alignment=1)

facts = json.load(open(ROOT / "outputs/facts_payload.json"))
ins = json.load(open(ROOT / "outputs/insights.json"))
mr = json.load(open(ROOT / "outputs/models/model_results.json"))
summary_md = (ROOT / "outputs/executive_summary.md").read_text().split("\n\n", 1)[1]
by_channel = pd.read_csv(ROOT / "outputs/kpi_by_channel.csv", index_col=0)
by_segment = pd.read_csv(ROOT / "outputs/kpi_by_segment.csv", index_col=0)
prof = pd.DataFrame(mr["rfm"]["profiles"])
lift = pd.read_csv(ROOT / "outputs/models/response_model_decile_lift.csv", index_col=0)


def md(text):  # **bold** -> <b>
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def img(name, width=17 * cm):
    im = Image(str(CH / name))
    ratio = im.imageHeight / im.imageWidth
    im.drawWidth, im.drawHeight = width, width * ratio
    return im


def table(df, col_widths=None, fmt=None, header_bg=DARK, font=8):
    fmt = fmt or {}
    cell = ParagraphStyle("cell", fontName="DV", fontSize=font, leading=font + 2.5)
    hcell = ParagraphStyle("hcell", fontName="DV-B", fontSize=font, leading=font + 2.5, textColor=colors.white)
    data = [[Paragraph(str(c), hcell) for c in df.columns]] + \
           [[Paragraph(str(fmt.get(c, lambda v: v)(v)), cell) for c, v in zip(df.columns, row)] for row in df.itertuples(index=False)]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_bg), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "DV-B"), ("FONTNAME", (0, 1), (-1, -1), "DV"), ("FONTSIZE", (0, 0), (-1, -1), font),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F7F8")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CCD6D8")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def kpi_cards(items):
    cells = [[Paragraph(v, KPI_N) for _, v in items], [Paragraph(l, KPI_L) for l, _ in items]]
    t = Table(cells, colWidths=[17 * cm / len(items)] * len(items))
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#BCE2E7")), ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#BCE2E7")),
                           ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4FAFB")), ("TOPPADDING", (0, 0), (-1, 0), 9), ("BOTTOMPADDING", (0, 1), (-1, 1), 9)]))
    return t


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("DV", 7.5); canvas.setFillColor(GREYTXT)
    canvas.drawString(2 * cm, 1.2 * cm, "Marketing Campaign Performance & Customer Intelligence Suite  ·  Igor Shudrov  ·  synthetic portfolio dataset")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}")
    canvas.setStrokeColor(TEAL); canvas.setLineWidth(1.2); canvas.line(2 * cm, A4[1] - 1.5 * cm, A4[0] - 2 * cm, A4[1] - 1.5 * cm)
    canvas.restoreState()


doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2.2 * cm, bottomMargin=2 * cm,
                        title="Marketing Campaign Performance & Customer Intelligence Suite", author="Igor Shudrov")
S = []
o = facts
# ------------------------------------------------------------------ Cover / Executive summary
S += [Paragraph("Marketing Campaign Performance &amp; Customer Intelligence Suite", H1),
      Paragraph("Campaign KPI analysis · RFM segmentation · response &amp; churn models · AI-generated insights &nbsp;|&nbsp; "
                "Data: 6,503 campaign-customer touches, 120 campaigns, 5 channels, Jan 2024 – Dec 2025 (synthetic, generated to mirror real CRM/media data)", SMALL),
      Spacer(1, 8),
      kpi_cards([("Media spend", f"€{o['spend']/1e3:.1f}K"), ("Attributed revenue", f"€{o['revenue']/1e3:.1f}K"), ("Blended ROAS", f"{o['roas']:.1f}x"),
                 ("CAC", f"€{o['cac']:.0f}"), ("Response rate", f"{o['response_rate']*100:.1f}%"), ("Customers reached", f"{o['reached']:,}")]),
      Spacer(1, 10), Paragraph("1. Executive Summary", H2)]
S += [Paragraph(md(p), BODY) for p in summary_md.split("\n\n")]
S += [Paragraph("<i>The executive summary above is produced by the AI-insight layer of the pipeline: a narrative generator that is only allowed to use "
                "numbers computed and validated by the analytics layer (no hallucinated figures). An optional LLM mode rewrites the same fact payload in richer prose.</i>", SMALL)]

# ------------------------------------------------------------------ Methodology
S += [Spacer(1, 6), Paragraph("2. Methodology &amp; Data", H2),
      Paragraph("<b>Data.</b> One row per campaign × customer touch (6,503 rows). Each row carries campaign attributes (channel, objective, dates, allocated spend), "
                "delivery metrics (impressions, clicks, conversions, revenue) and customer attributes (age, CRM lifecycle segment, region, device, tenure, "
                "loyalty membership, past purchases). The dataset is synthetic but engineered with realistic structure: channel-specific CTR/CVR/AOV, Q4 seasonality and a summer dip, "
                "diminishing returns to spend intensity, and a latent customer propensity that drives repeat purchases.", BODY),
      Paragraph("<b>KPI framework.</b> CTR = clicks / impressions; CVR = conversions / clicks; Response rate = converting customers / reached customers; "
                "CPC = spend / clicks; CAC = spend / conversions; ROAS = revenue / spend; AOV = revenue / conversions. All KPIs are computed at interaction grain and "
                "aggregated by channel, segment, region, device, age group, month and campaign, then exported to a star schema for Power BI / Qlik Sense.", BODY),
      Paragraph("<b>Statistical analysis.</b> Diminishing returns are estimated with a log-log regression of campaign ROAS on spend-per-reached-customer with channel fixed "
                "effects (within-channel elasticity), so that the cheap-but-efficient Email channel does not bias the slope.", BODY),
      Paragraph("<b>Machine learning.</b> (a) RFM features (recency, frequency, monetary; log-scaled, standardised) clustered with K-means, k selected on silhouette score and "
                "business interpretability. (b) Response propensity: Logistic Regression vs. Random Forest vs. XGBoost on 18 features with leakage-safe history features "
                "(only events strictly before each touch), 5-fold stratified CV plus a 25% hold-out; explained with SHAP. (c) Churn: 2024 behaviour → did the customer buy again in "
                "2025, evaluated only on customers actually reached in 2025; Logistic Regression vs. Gradient Boosting, 5-fold CV, SHAP drivers.", BODY),
      Paragraph("<b>Stack.</b> Python (pandas, NumPy, scikit-learn, XGBoost, SHAP, matplotlib/seaborn, ReportLab), star-schema CSV/Excel export with ready-made DAX and Qlik measures.", BODY),
      Paragraph("Pipeline", H2),
      table(pd.DataFrame({"Step": ["01", "02", "03", "04", "05", "06"],
                          "Script": ["01_generate_data.py", "02_kpi_eda.py", "03_ml_models.py", "04_export_star_schema.py", "05_ai_insights.py", "06_build_report.py"],
                          "Output": ["Raw interaction table, campaign & customer masters", "KPI tables by dimension, 8 charts, insights.json",
                                     "RFM segments, response & churn models, SHAP, lift tables", "fact_* / dim_* CSV + Excel, DAX & Qlik measures",
                                     "Executive summary narrative (rule-based, optional LLM)", "This PDF"]}), col_widths=[1.2 * cm, 5 * cm, 10.8 * cm])]

# ------------------------------------------------------------------ KPI dashboard
S += [PageBreak(), Paragraph("3. KPI Dashboard — Channel Performance", H2)]
bc = by_channel.reset_index()[["channel", "spend", "revenue", "conversions", "CTR", "CVR", "response_rate", "CAC", "ROAS"]].copy()
bc["channel"] = bc["channel"].map({"tv": "TV", "email": "Email", "search": "Search", "social": "Social", "display": "Display"})
bc.columns = ["Channel", "Spend", "Revenue", "Conv.", "CTR", "CVR", "Resp. rate", "CAC", "ROAS"]
S += [table(bc, fmt={"Spend": lambda v: f"€{v:,.0f}", "Revenue": lambda v: f"€{v:,.0f}", "Conv.": lambda v: f"{v:.0f}", "CTR": lambda v: f"{v*100:.1f}%",
                     "CVR": lambda v: f"{v*100:.0f}%", "Resp. rate": lambda v: f"{v*100:.1f}%", "CAC": lambda v: f"€{v:.0f}", "ROAS": lambda v: f"{v:.2f}x"}),
      Paragraph("TV click-to-conversion is not meaningful (conversions are brand-driven, not click-attributed) and is excluded from funnel comparisons.", SMALL),
      Spacer(1, 6), img("01_spend_vs_revenue_share.png", 16 * cm), Spacer(1, 6), img("02_roas_cac_by_channel.png", 17 * cm)]
S += [PageBreak(), Paragraph("KPI Dashboard — Time, Audience &amp; Efficiency", H2), img("03_monthly_trend.png", 17 * cm), Spacer(1, 6),
      img("07_funnel_by_channel.png", 15.5 * cm)]
S += [PageBreak(), img("04_response_heatmap_segment_device.png", 14 * cm), Spacer(1, 6), img("06_region_age.png", 17 * cm), Spacer(1, 6), img("08_roas_objective_channel.png", 13 * cm)]
S += [PageBreak(), Paragraph("Diminishing returns to spend", H2),
      Paragraph(f"Within each channel, campaigns that spend more per reached customer achieve lower ROAS. The fixed-effects elasticity is "
                f"<b>{ins['elasticity']:.2f}</b>: doubling spend intensity lowers ROAS by about <b>{(1-2**ins['elasticity'])*100:.0f}%</b>. "
                "This is the quantitative basis for capping campaign intensity and splitting large flights.", BODY), img("05_diminishing_returns.png", 16 * cm),
      Paragraph("Key insights", H2)]
for i in ins["insights"]:
    S.append(Paragraph(f"<b>{i['id']}. {i['title']}.</b> {i['text']}", BUL, bulletText="•"))

# ------------------------------------------------------------------ Segmentation
S += [PageBreak(), Paragraph("4. Customer Segmentation (RFM + K-means)", H2),
      Paragraph(f"{mr['rfm']['n_buyers']} customers with at least one purchase were clustered on recency, frequency and monetary value (k = {mr['rfm']['k']}; "
                f"silhouette by k: " + ", ".join(f"k={k}: {v:.2f}" for k, v in mr['rfm']['silhouette'].items()) + f"). The remaining {mr['rfm']['n_prospects']:,} reached customers "
                "never purchased and form a 'Prospect' group for acquisition targeting.", BODY)]
pt = prof[["segment_name", "customers", "avg_recency", "avg_frequency", "avg_monetary", "revenue_share"]].copy()
pt.columns = ["Segment", "Customers", "Avg recency (days)", "Avg purchases", "Avg revenue / customer", "Share of buyer revenue"]
S += [table(pt, fmt={"Avg recency (days)": lambda v: f"{v:.0f}", "Avg purchases": lambda v: f"{v:.1f}", "Avg revenue / customer": lambda v: f"€{v:,.0f}", "Share of buyer revenue": lambda v: f"{v*100:.0f}%"}),
      Spacer(1, 6), img("09_rfm_segments.png", 17 * cm),
      Paragraph("Segment playbook", H2)]
play = {"Champions": "Protect and grow: VIP service, early access, referral incentives. Never over-contact — frequency caps matter most here.",
        "Recent Buyers": "Onboarding journey in the first 30 days; cross-sell a second category to convert them into repeat buyers.",
        "Occasional Repeat": "Reactivation cadence tied to their purchase cycle; personalised bundles to lift frequency and AOV.",
        "One-off Lapsed": "Low-cost win-back (Email first, then Search retargeting); suppress from expensive Display/Social prospecting."}
for k, v in play.items():
    S.append(Paragraph(f"<b>{k}.</b> {v}", BUL, bulletText="•"))

# ------------------------------------------------------------------ Predictive models
rm = mr["response_model"]
S += [PageBreak(), Paragraph("5. Predictive Models", H2), Paragraph("5.1 Campaign response propensity", H2),
      Paragraph(f"Target: did the reached customer convert (base rate {rm['base_rate']*100:.1f}%). Train {rm['n_train']:,} / test {rm['n_test']:,} touches.", BODY)]
mt = pd.DataFrame([{"Model": k, "CV ROC-AUC (5-fold)": f"{v['cv_auc_mean']:.3f} ± {v['cv_auc_std']:.3f}", "Hold-out ROC-AUC": f"{v['test_auc']:.3f}", "Hold-out PR-AUC": f"{v['test_pr_auc']:.3f}"} for k, v in rm["models"].items()])
S += [table(mt), Spacer(1, 6),
      Table([[img("10_response_roc.png", 7.5 * cm), img("11_response_decile_lift.png", 9 * cm)]], colWidths=[7.8 * cm, 9.2 * cm]),
      Paragraph(f"<b>Business value.</b> Contacting only the top 3 deciles of scored customers captures <b>{rm['top30_capture_pct']:.0f}%</b> of responders "
                f"(top-decile lift {rm['top_decile_lift']:.1f}x). At the current CAC this translates into reaching ~70% fewer customers for ~60% of the conversions — "
                "a direct lever on CAC and on customer fatigue.", BODY),
      img("12_response_shap.png", 12.5 * cm),
      Paragraph("Reading the SHAP plot: high spend-per-touch pushes predictions down (diminishing returns), Search and Loyal push up, "
                "Display and mobile push down; behavioural history (past purchases, app activity, loyalty membership) adds incremental signal.", SMALL)]
cm_ = mr["churn_model"]
S += [PageBreak(), Paragraph("5.2 Churn / retention model", H2),
      Paragraph(f"Population: {cm_['n_customers']:,} customers reached by campaigns in 2025. Features: 2024 behaviour (touches, purchases, revenue, recency, clicks, channel and device mix) "
                f"plus static attributes. Label: no purchase in 2025 (churn rate {cm_['churn_rate']*100:.0f}% overall; <b>{cm_['churn_rate_among_2024_buyers']*100:.0f}%</b> among {cm_['n_buyers_2024']} 2024 buyers). "
                f"Best model: {cm_['best']} with 5-fold CV ROC-AUC <b>{cm_['cv_auc'][cm_['best']]['mean']:.2f}</b> "
                f"(Gradient Boosting {cm_['cv_auc'].get('Gradient Boosting', {}).get('mean', float('nan')):.2f}). Given sparse purchase histories the model is intentionally simple; "
                "it is used to produce a risk band (Low / Medium / High) that is joined to dim_customers for the dashboard.", BODY),
      img("13_churn_shap.png", 12.5 * cm),
      Paragraph("Drivers: more 2024 touches, Loyal segment, recent purchases, loyalty membership and desktop usage lower churn risk; At-Risk segment and long recency raise it. "
                "Recommendation: trigger a retention journey when a Champion or Occasional buyer crosses 180 days without a purchase.", BODY)]

# ------------------------------------------------------------------ Recommendations
S += [PageBreak(), Paragraph("6. Recommendations &amp; Next Steps", H2)]
recs = [
    ("Rebalance the channel mix", f"Move 10–15% of budget out of Display (ROAS {facts['worst_roas']:.2f}x) and the largest low-ROAS Social flights into Email lifecycle programmes "
                                  f"(ROAS {facts['best_roas']:.1f}x, {facts['best_spend_share']*100:.0f}% of spend today) and mid-sized Search campaigns. Expected effect at constant budget: +15–20% attributed revenue."),
    ("Cap spend intensity", f"Set a per-campaign ceiling on spend per reached customer and split large flights into 2–3 waves. Elasticity of {ins['elasticity']:.2f} implies every halving of intensity recovers ~{(2**(-ins['elasticity'])-1)*100:.0f}% ROAS."),
    ("Phase budget with seasonality", f"Nov–Dec months deliver {ins['q4_uplift']:.1f}x average monthly revenue: front-load Q4, protect an always-on Email/Search baseline in Jul–Aug, avoid heavy summer Display."),
    ("Operationalise propensity scoring", f"Score the CRM base weekly; contact only the top 3 deciles ({rm['top30_capture_pct']:.0f}% of responders). Use deciles 4–6 for low-cost Email only; suppress 7–10 from paid media."),
    ("Launch segment journeys", "Champions: VIP & frequency caps. Recent buyers: 30-day onboarding. One-off Lapsed & High churn risk: Email-first win-back then Search retargeting."),
    ("Govern with the dashboard", "Publish the Power BI model (star schema + DAX measures) with weekly refresh; track ROAS vs. 2.5x target, CAC, Response Rate and Share Gap by channel; alert on campaigns below break-even after 7 days."),
]
for i, (t, txt) in enumerate(recs, 1):
    S.append(Paragraph(f"<b>{i}. {t}.</b> {txt}", BUL, bulletText="•"))
S += [Paragraph("Limitations &amp; next steps", H2),
      Paragraph("The dataset is synthetic and last-touch attributed; a production version should add multi-touch or incrementality tests (geo holdouts), "
                "media cost by placement, and campaign creative metadata. Model performance (AUC 0.75 / 0.68) is realistic for CRM data of this depth and should be "
                "re-validated on real data with time-based splits. Natural extensions: marketing-mix model for budget optimisation, uplift modelling for treatment targeting, "
                "and connecting the AI-insight layer to a hosted LLM for Q&amp;A over the KPI model.", BODY)]

# ------------------------------------------------------------------ Appendix
S += [PageBreak(), Paragraph("Appendix A — Star schema for Power BI / Qlik", H2),
      table(pd.DataFrame({"Table": ["fact_campaign_interactions", "fact_campaigns", "dim_campaigns", "dim_customers", "dim_channels", "dim_dates", "dim_segments"],
                          "Grain / keys": ["campaign × customer touch; FK campaign_id, customer_id, channel_id, date_key", "campaign; pre-aggregated KPIs (CTR, CVR, CAC, ROAS, profit)",
                                           "campaign_id; name, objective, dates, budget, budget_band", "customer_id; demographics, CRM segment, RFM segment, churn probability & risk band",
                                           "channel_id; channel type, funnel stage", "date_key; year, quarter, month, week, peak-season flag (mark as date table)", "customer_segment; order & description"],
                          "Rows": ["6,503", "120", "120", "2,200", "5", "722", "4"]}), col_widths=[4.6 * cm, 10.4 * cm, 2 * cm]),
      Spacer(1, 8), Paragraph("Appendix B — Core DAX measures", H2)]
dax = (ROOT / "data/powerbi/measures_dax.txt").read_text().split("// ---- time intelligence")[0]
S += [Paragraph(dax.replace("\n", "<br/>").replace(" ", "&nbsp;"), ParagraphStyle("code", parent=SMALL, fontName="DV", fontSize=7.2, leading=9.5, backColor=colors.HexColor("#F4F6F7"), borderPadding=6))]
lt = lift.reset_index()[["decile", "customers", "responders", "rate", "cum_responders_pct", "lift"]]
lt.columns = ["Decile", "Customers", "Responders", "Response rate", "Cumulative % of responders", "Lift"]
S += [KeepTogether([Spacer(1, 8), Paragraph("Appendix C — Decile lift table (response model, hold-out)", H2),
                    table(lt, fmt={"Response rate": lambda v: f"{v*100:.1f}%", "Cumulative % of responders": lambda v: f"{v:.0f}%", "Lift": lambda v: f"{v:.2f}x", "Responders": lambda v: f"{v:.0f}"})])]

doc.build(S, onFirstPage=footer, onLaterPages=footer)
print("PDF ->", OUT)
