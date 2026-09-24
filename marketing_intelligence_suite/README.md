# Marketing Campaign Performance & Customer Intelligence Suite

End-to-end marketing analytics portfolio project: KPI framework → EDA & insights → RFM segmentation → response & churn models → Power BI star schema → AI-generated executive summary → stakeholder PDF report.

**Headline results (synthetic dataset, 6,503 campaign-customer touches, 120 campaigns, Jan 2024 – Dec 2025)**

| Metric | Value |
|---|---|
| Media spend / attributed revenue | €53.1K / €194.4K (blended ROAS 3.7x, CAC €66) |
| Best channel | Email — ROAS 6.5x, CAC €31, only 6% of spend |
| Worst channel | Display — ROAS 0.84x (below break-even) |
| Diminishing returns | within-channel elasticity −0.71 (2x intensity → −39% ROAS) |
| Seasonality | Nov–Dec revenue 1.4x an average month |
| Response model | Random Forest, hold-out ROC-AUC 0.75, top-decile lift 3.2x, top 30% of scores = 62% of responders |
| Churn model | Logistic Regression, CV AUC 0.68; 76% of 2024 buyers did not repurchase in 2025 |
| Segmentation | RFM + K-means (k=4): Champions = 9% of buyers, 24% of revenue |

## Repository layout
```
src/
  01_generate_data.py       synthetic data with realistic structure (channel economics, seasonality, diminishing returns)
  02_kpi_eda.py             KPI tables by dimension, 8 charts, insights.json
  03_ml_models.py           RFM/K-means, response model (LR/RF/XGB + SHAP + lift), churn model (+ SHAP)
  04_export_star_schema.py  fact_* / dim_* CSV + Excel, DAX & Qlik measures
  05_ai_insights.py         AI-insight layer: executive summary from validated facts (optional LLM mode)
  06_build_report.py        12-page stakeholder PDF (ReportLab)
data/raw/                   marketing_interactions.csv, campaigns_master.csv, customers_master.csv, customer_rfm_segments.csv
data/powerbi/               star schema (7 tables), marketing_star_schema.xlsx, measures_dax.txt, measures_qlik.txt
outputs/charts/             13 charts (PNG)
outputs/models/             model_results.json, feature importances, decile lift, churn scores, .joblib models
outputs/executive_summary.md, insights.json, kpi_by_*.csv
report/Marketing_Campaign_Performance_Report.pdf
CV_LinkedIn_PowerBI_Guide.md   CV bullets, LinkedIn text, 30–60 min Power BI build guide
```

## Run
```bash
pip install -r requirements.txt
bash run_all.sh          # ~2-3 minutes end to end
```
Optional LLM mode for the summary: `export OPENAI_API_KEY=...` before running `05_ai_insights.py` (uses `generate_executive_summary_llm`).

## Stack
Python 3 · pandas · NumPy · scikit-learn · XGBoost · SHAP · matplotlib / seaborn · ReportLab · Power BI (DAX) / Qlik Sense
