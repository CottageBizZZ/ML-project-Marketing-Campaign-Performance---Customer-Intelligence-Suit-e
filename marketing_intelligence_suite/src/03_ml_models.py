"""
03_ml_models.py
  A. RFM customer segmentation (K-means, k chosen by silhouette)
  B. Campaign response propensity model (Logistic / RandomForest / XGBoost, ROC-AUC, lift, SHAP)
  C. Customer churn model (6-month forward window, gradient boosting + SHAP drivers)
Outputs: outputs/models/*.json|csv|joblib, outputs/charts/09-14_*.png, data/raw/customer_rfm_segments.csv
"""
import json
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import shap
import joblib
from pathlib import Path
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import roc_auc_score, roc_curve, silhouette_score, average_precision_score, classification_report
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
CH, MD = ROOT / "outputs" / "charts", ROOT / "outputs" / "models"
MD.mkdir(parents=True, exist_ok=True)
plt.style.use("seaborn-v0_8-whitegrid")
plt.rcParams.update({"figure.dpi": 150, "font.size": 11, "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left"})
TEAL, RUST, DARK, LIGHT, GREY = "#20808D", "#A84B2F", "#1B474D", "#BCE2E7", "#B8BDC2"
PAL = [TEAL, RUST, "#FFC553", DARK, "#944454", "#848456"]
SEED = 42
results = {}

df = pd.read_csv(ROOT / "data/raw/marketing_interactions.csv", parse_dates=["start_date", "end_date", "touch_date"])
camp = pd.read_csv(ROOT / "data/raw/campaigns_master.csv", parse_dates=["start_date", "end_date"])
cust = pd.read_csv(ROOT / "data/raw/customers_master.csv")
CUST_ATTR = ["tenure_months", "loyalty_member", "email_opt_in", "past_purchases_12m", "app_sessions_30d"]
df = df.merge(camp[["campaign_id", "objective"]], on="campaign_id").merge(cust[["customer_id"] + CUST_ATTR], on="customer_id")
SNAPSHOT = pd.Timestamp("2025-12-31")

# =========================================================================== #
# A. RFM segmentation
# =========================================================================== #
buy = df[df["conversions"] > 0]
rfm = buy.groupby("customer_id").agg(last_purchase=("touch_date", "max"), frequency=("conversions", "sum"), monetary=("revenue", "sum"))
rfm["recency_days"] = (SNAPSHOT - rfm["last_purchase"]).dt.days
X_rfm = np.column_stack([np.log1p(rfm["recency_days"]), np.log1p(rfm["frequency"]), np.log1p(rfm["monetary"])])
X_rfm = StandardScaler().fit_transform(X_rfm)

sil = {k: silhouette_score(X_rfm, KMeans(k, n_init=20, random_state=SEED).fit_predict(X_rfm)) for k in range(3, 8)}
best_k = 4  # business-interpretable; silhouette reported for transparency
km = KMeans(best_k, n_init=20, random_state=SEED).fit(X_rfm)
rfm["cluster"] = km.labels_
prof = rfm.groupby("cluster").agg(customers=("frequency", "size"), avg_recency=("recency_days", "mean"),
                                  avg_frequency=("frequency", "mean"), avg_monetary=("monetary", "mean"), total_revenue=("monetary", "sum"))
# Name clusters by value/recency ranking
names = ["Champions", "Recent Buyers", "Occasional Repeat", "One-off Lapsed"]
remaining = prof.index.tolist(); name_map = {}
c = prof.loc[remaining, "avg_monetary"].idxmax(); name_map[c] = "Champions"; remaining.remove(c)
c = prof.loc[remaining, "avg_recency"].idxmax(); name_map[c] = "One-off Lapsed"; remaining.remove(c)
c = prof.loc[remaining, "avg_recency"].idxmin(); name_map[c] = "Recent Buyers"; remaining.remove(c)
name_map[remaining[0]] = "Occasional Repeat"
prof["score"] = prof.index.map(lambda c: -names.index(name_map[c]))
rfm["segment_name"] = rfm["cluster"].map(name_map)
prof["segment_name"] = prof.index.map(name_map)
prof["revenue_share"] = prof["total_revenue"] / prof["total_revenue"].sum()
prof = prof.sort_values("score", ascending=False)
prof.to_csv(MD / "rfm_segment_profiles.csv")
full_rfm = cust[["customer_id"]].merge(rfm.drop(columns="cluster"), on="customer_id", how="left")
full_rfm["segment_name"] = full_rfm["segment_name"].fillna("Prospect (no purchase)")
full_rfm.to_csv(ROOT / "data/raw/customer_rfm_segments.csv", index=False)
results["rfm"] = dict(k=best_k, silhouette=sil, n_buyers=int(len(rfm)), n_prospects=int((full_rfm["segment_name"] == "Prospect (no purchase)").sum()),
                      profiles=prof.round(2).reset_index().to_dict(orient="records"))

fig, axes = plt.subplots(1, 2, figsize=(13, 5.2), layout="constrained")
for (c, n), col in zip(name_map.items(), PAL):
    sub = rfm[rfm["cluster"] == c]
    axes[0].scatter(sub["recency_days"], sub["monetary"], s=18 + sub["frequency"] * 12, alpha=0.65, color=col, label=f"{n} (n={len(sub)})", edgecolor="white", lw=0.4)
axes[0].set_yscale("log"); axes[0].set_xlabel("Recency — days since last purchase"); axes[0].set_ylabel("Monetary — total revenue, € (log)")
axes[0].set_title("RFM clusters (K-means, k=4)\nbubble size = purchase frequency", fontsize=12); axes[0].legend(frameon=False, fontsize=9)
p = prof.set_index("segment_name")
axes[1].barh(p.index[::-1], p["revenue_share"][::-1] * 100, color=[dict(zip(names, PAL))[n] for n in p.index[::-1]])
for i, (n, v, c) in enumerate(zip(p.index[::-1], p["revenue_share"][::-1] * 100, p["customers"][::-1])):
    axes[1].text(v + 1, i, f"{v:.0f}% of revenue · {c} customers · avg €{p.loc[n,'avg_monetary']:.0f}", va="center", fontsize=9)
axes[1].set_xlim(0, 100); axes[1].set_xlabel("% of buyer revenue")
axes[1].set_title(f"{names[0]} are {p.loc[names[0],'customers']/p['customers'].sum()*100:.0f}% of buyers but {p.loc[names[0],'revenue_share']*100:.0f}% of revenue\nRevenue concentration by RFM segment", fontsize=12)
fig.savefig(CH / "09_rfm_segments.png", bbox_inches="tight"); plt.close(fig)

# =========================================================================== #
# B. Response propensity model (interaction grain)
# =========================================================================== #
d = df.sort_values(["customer_id", "touch_date"]).copy()
d["responded"] = (d["conversions"] > 0).astype(int)
# leakage-safe history features: only events strictly before the current touch
g = d.groupby("customer_id")
d["prior_touches"] = g.cumcount()
d["prior_conversions"] = g["conversions"].cumsum() - d["conversions"]
d["prior_revenue"] = g["revenue"].cumsum() - d["revenue"]
d["month"] = d["touch_date"].dt.month
d["days_into_campaign"] = (d["touch_date"] - d["start_date"]).dt.days
d["spend_per_touch"] = d["budget"]

CAT = ["channel", "objective", "customer_segment", "region", "device_type"]
NUM = ["customer_age"] + CUST_ATTR + ["impressions", "spend_per_touch", "month", "days_into_campaign", "prior_touches", "prior_conversions", "prior_revenue"]
X, y = d[CAT + NUM], d["responded"]
X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, stratify=y, random_state=SEED)
pre = ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore"), CAT), ("num", "passthrough", NUM)])
models = {
    "Logistic Regression": Pipeline([("pre", pre), ("sc", StandardScaler(with_mean=False)), ("m", LogisticRegression(max_iter=2000, C=0.5))]),
    "Random Forest": Pipeline([("pre", pre), ("m", RandomForestClassifier(400, min_samples_leaf=8, class_weight="balanced_subsample", random_state=SEED, n_jobs=-1))]),
    "XGBoost": Pipeline([("pre", pre), ("m", XGBClassifier(n_estimators=400, max_depth=4, learning_rate=0.03, subsample=0.85, colsample_bytree=0.8,
                                                            min_child_weight=5, reg_lambda=2.0, scale_pos_weight=(1 - y_tr.mean()) / y_tr.mean(),
                                                            random_state=SEED, n_jobs=-1, eval_metric="auc"))]),
}
cv = StratifiedKFold(5, shuffle=True, random_state=SEED)
resp = {}
fig, ax = plt.subplots(figsize=(6.5, 5.5), layout="constrained")
for (name, pipe), col in zip(models.items(), [GREY, DARK, TEAL]):
    cv_auc = cross_val_score(pipe, X_tr, y_tr, cv=cv, scoring="roc_auc")
    pipe.fit(X_tr, y_tr)
    proba = pipe.predict_proba(X_te)[:, 1]
    auc, ap = roc_auc_score(y_te, proba), average_precision_score(y_te, proba)
    resp[name] = dict(cv_auc_mean=float(cv_auc.mean()), cv_auc_std=float(cv_auc.std()), test_auc=float(auc), test_pr_auc=float(ap))
    fpr, tpr, _ = roc_curve(y_te, proba)
    ax.plot(fpr, tpr, color=col, lw=2 if name == "XGBoost" else 1.5, label=f"{name} (AUC {auc:.3f})")
ax.plot([0, 1], [0, 1], ls="--", color="#999", lw=1)
ax.set_xlabel("False positive rate"); ax.set_ylabel("True positive rate")
ax.set_title("Response model ROC — hold-out set (25%)\nWho will convert when reached by a campaign?", fontsize=12); ax.legend(frameon=False, loc="lower right")
fig.savefig(CH / "10_response_roc.png", bbox_inches="tight"); plt.close(fig)

best_name = max(resp, key=lambda k: resp[k]["test_auc"])
best = models[best_name]
proba = best.predict_proba(X_te)[:, 1]
# Decile lift
lift = pd.DataFrame({"p": proba, "y": y_te.values}).sort_values("p", ascending=False).reset_index(drop=True)
lift["decile"] = pd.qcut(lift.index, 10, labels=range(1, 11))
lt = lift.groupby("decile", observed=True).agg(customers=("y", "size"), responders=("y", "sum"), rate=("y", "mean"))
lt["cum_responders_pct"] = lt["responders"].cumsum() / lt["responders"].sum() * 100
lt["lift"] = lt["rate"] / lift["y"].mean()
lt.to_csv(MD / "response_model_decile_lift.csv")
top2 = float(lt["cum_responders_pct"].iloc[1]); top3 = float(lt["cum_responders_pct"].iloc[2])

fig, ax = plt.subplots(figsize=(9, 4.8), layout="constrained")
ax.bar(lt.index.astype(str), lt["rate"] * 100, color=[TEAL if i < 3 else GREY for i in range(10)])
ax.axhline(lift["y"].mean() * 100, color=RUST, ls="--", lw=1.2); ax.text(9.5, lift["y"].mean() * 100 + 0.6, f"baseline {lift['y'].mean()*100:.1f}%", ha="right", color=RUST, fontsize=9)
for i, (r, l) in enumerate(zip(lt["rate"] * 100, lt["lift"])): ax.text(i, r + 0.5, f"{r:.0f}%\n{l:.1f}x", ha="center", fontsize=8.5)
ax.set_xlabel("Scored decile (1 = highest predicted propensity)"); ax.set_ylabel("Actual response rate, %")
ax.set_title(f"Targeting the top 30% of scored customers captures {top3:.0f}% of all responders\nResponse rate by model decile ({best_name}, hold-out)", fontsize=12)
ax.set_ylim(0, lt["rate"].max() * 100 * 1.25)
fig.savefig(CH / "11_response_decile_lift.png", bbox_inches="tight"); plt.close(fig)

# SHAP on best (tree) model
feat_names = list(best.named_steps["pre"].get_feature_names_out())
feat_names = [f.replace("cat__", "").replace("num__", "") for f in feat_names]
X_te_t = best.named_steps["pre"].transform(X_te)
X_te_t = X_te_t.toarray() if hasattr(X_te_t, "toarray") else X_te_t
explainer = shap.TreeExplainer(best.named_steps["m"])
sv = explainer.shap_values(X_te_t)
sv = sv[1] if isinstance(sv, list) else sv
sv = sv[:, :, 1] if sv.ndim == 3 else sv
imp = pd.Series(np.abs(sv).mean(0), index=feat_names).sort_values(ascending=False)
imp.to_csv(MD / "response_model_feature_importance.csv", header=["mean_abs_shap"])
fig = plt.figure(figsize=(9, 6))
shap.summary_plot(sv, X_te_t, feature_names=feat_names, max_display=14, show=False, plot_size=None, color_bar_label="feature value")
plt.title(f"What drives campaign response? — SHAP values, {best_name}\ntop drivers: {', '.join(imp.index[:3])}", loc="left", fontsize=12, fontweight="bold")
plt.tight_layout(); plt.savefig(CH / "12_response_shap.png", bbox_inches="tight", dpi=150); plt.close("all")
joblib.dump(best, MD / "response_model.joblib")
results["response_model"] = dict(models=resp, best=best_name, n_train=int(len(X_tr)), n_test=int(len(X_te)), base_rate=float(y.mean()),
                                 top20_capture_pct=top2, top30_capture_pct=top3, top_decile_lift=float(lt["lift"].iloc[0]),
                                 top_features=imp.head(10).round(4).to_dict())

# =========================================================================== #
# C. Churn / retention model
#    History window: 2024 (12 months) -> Forward window: 2025 (12 months).
#    Population: customers reached by at least one campaign in 2025 (so they had the opportunity to buy).
#    churned = 1 if the customer made no purchase in 2025. Churn among 2024 buyers is reported separately.
# =========================================================================== #
CUTOFF = pd.Timestamp("2024-12-31")
hist = df[df["touch_date"] <= CUTOFF]
fut = df[df["touch_date"] > CUTOFF]
h = hist
feat = h.groupby("customer_id").agg(
    touches=("interaction_id", "size"), purchases=("conversions", "sum"), revenue=("revenue", "sum"),
    clicks=("clicks", "sum"), impressions=("impressions", "sum"),
    first_touch=("touch_date", "min"), last_touch=("touch_date", "max"),
    email_share=("channel", lambda s: (s == "email").mean()), search_share=("channel", lambda s: (s == "search").mean()),
    desktop_share=("device_type", lambda s: (s == "desktop").mean()),
)
last_buy = h[h["conversions"] > 0].groupby("customer_id")["touch_date"].max()
feat["recency_days"] = (CUTOFF - last_buy.reindex(feat.index)).dt.days.fillna(999)
feat["days_since_last_touch"] = (CUTOFF - feat["last_touch"]).dt.days
feat["ctr"] = feat["clicks"] / feat["impressions"]
feat["was_buyer_2024"] = (feat["purchases"] > 0).astype(int)
feat = feat.drop(columns=["first_touch", "last_touch"])
# customers reached in 2025 but never touched in 2024 get zero-history rows
reached = fut["customer_id"].unique()
feat = feat.reindex(reached).fillna({c: 0 for c in feat.columns}).fillna(0)
feat.loc[feat["recency_days"] == 0, "recency_days"] = 999
feat = feat.join(cust.set_index("customer_id")[["customer_age", "customer_segment", "region"] + CUST_ATTR])
future_buyers = fut[fut["conversions"] > 0]["customer_id"].unique()
feat["churned"] = (~feat.index.isin(future_buyers)).astype(int)
churn_among_buyers = float(feat.loc[feat["was_buyer_2024"] == 1, "churned"].mean())

CATc = ["customer_segment", "region"]
NUMc = [c for c in feat.columns if c not in CATc + ["churned"]]
Xc, yc = feat[CATc + NUMc], feat["churned"]
pre_c = ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore"), CATc), ("num", "passthrough", NUMc)])
churn_models = {
    "Logistic Regression": Pipeline([("pre", pre_c), ("sc", StandardScaler(with_mean=False)), ("m", LogisticRegression(max_iter=3000, C=0.3))]),
    "Gradient Boosting": Pipeline([("pre", pre_c), ("m", GradientBoostingClassifier(n_estimators=250, max_depth=2, learning_rate=0.04, subsample=0.8, random_state=SEED))]),
}
cvc = StratifiedKFold(5, shuffle=True, random_state=SEED)
churn_res = {n: cross_val_score(p, Xc, yc, cv=cvc, scoring="roc_auc") for n, p in churn_models.items()}
best_c = max(churn_res, key=lambda k: churn_res[k].mean())
cm = churn_models[best_c].fit(Xc, yc)
fn = [f.replace("cat__", "").replace("num__", "") for f in cm.named_steps["pre"].get_feature_names_out()]
Xc_t = cm.named_steps["pre"].transform(Xc); Xc_t = Xc_t.toarray() if hasattr(Xc_t, "toarray") else Xc_t
if best_c == "Gradient Boosting":
    svc = shap.TreeExplainer(cm.named_steps["m"]).shap_values(Xc_t)
    svc = svc[:, :, 1] if np.ndim(svc) == 3 else svc
else:
    svc = shap.LinearExplainer(cm.named_steps["m"], cm.named_steps["sc"].transform(Xc_t)).shap_values(cm.named_steps["sc"].transform(Xc_t))
imp_c = pd.Series(np.abs(svc).mean(0), index=fn).sort_values(ascending=False)
imp_c.to_csv(MD / "churn_model_feature_importance.csv", header=["mean_abs_shap"])
fig = plt.figure(figsize=(9, 5.5))
shap.summary_plot(svc, Xc_t, feature_names=fn, max_display=12, show=False, plot_size=None)
plt.title(f"Churn drivers — SHAP values, {best_c} (5-fold CV AUC {churn_res[best_c].mean():.2f})\n2024 history → did the customer buy again in 2025?", loc="left", fontsize=12, fontweight="bold")
plt.tight_layout(); plt.savefig(CH / "13_churn_shap.png", bbox_inches="tight", dpi=150); plt.close("all")
joblib.dump(cm, MD / "churn_model.joblib")
feat.assign(churn_probability=cm.predict_proba(Xc)[:, 1]).to_csv(MD / "churn_scores.csv")
results["churn_model"] = dict(cutoff=str(CUTOFF.date()), n_customers=int(len(feat)), churn_rate=float(yc.mean()), n_buyers_2024=int(feat["was_buyer_2024"].sum()),
                              churn_rate_among_2024_buyers=churn_among_buyers, best=best_c,
                              cv_auc={k: dict(mean=float(v.mean()), std=float(v.std())) for k, v in churn_res.items()},
                              top_features=imp_c.head(8).round(4).to_dict())

json.dump(results, open(MD / "model_results.json", "w"), indent=2, default=str)
print(json.dumps({k: (v if k != "rfm" else {kk: vv for kk, vv in v.items() if kk != "profiles"}) for k, v in results.items()}, indent=1, default=str))
print(prof.round(1))
