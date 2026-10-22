"""Synthetic SaaS product and reliability intelligence workspace."""

import json

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from product.analytics import (
    adoption,
    between,
    conversion_trend,
    engagement,
    funnel,
    reliability,
    retention,
    returning_percentage,
    utc,
)
from product.detection import detect, evaluate, isolation
from product.generation import FEATURES, generate
from product.investigation import investigate
from product.pipeline import ingest
from product.reporting import TASKS, html_report, safe_evidence, summarize
from product.services import load

st.set_page_config(page_title="Product Intelligence", page_icon="◈", layout="wide")
st.markdown(
    "<style>.block-container{padding-top:2rem}"
    "[data-testid=stMetric]{background:#eef4fa;padding:18px;border-radius:10px;"
    "color:#102a43}</style>",
    unsafe_allow_html=True,
)
st.title("Product Intelligence")
st.caption("SYNTHETIC SaaS DATA / PRODUCT HEALTH / EVIDENCE-BASED INVESTIGATION")
page = st.sidebar.radio(
    "Workspace",
    [
        "Executive Overview",
        "Feature Adoption",
        "Conversion Funnel",
        "Reliability",
        "Anomaly Investigation",
        "AI Analyst",
    ],
)
selected = st.sidebar.date_input(
    "UTC date range (inclusive)",
    value=(pd.Timestamp("2025-01-01").date(), pd.Timestamp("2025-03-31").date()),
)
segment = st.sidebar.selectbox("User segment", ["all", "starter", "enterprise"])
if len(selected) != 2:
    st.info("Select start and end dates.")
    st.stop()
start = utc(selected[0])
end = utc(selected[1]) + pd.Timedelta(days=1)
if start >= end:
    st.warning("Select an ordered range.")
    st.stop()
if st.sidebar.button("Load / regenerate seed 42"):
    try:
        ingest(generate(), replace=True)
        st.sidebar.success("Validated scenario upserted; run recorded.")
    except Exception as exc:
        st.sidebar.error(f"Pipeline failed ({type(exc).__name__}); review run audit.")
try:
    data = load(str(end), segment)
except SQLAlchemyError:
    st.error(
        "Database unavailable or not migrated. Run alembic upgrade head then product.pipeline."
    )
    st.stop()
if data["events"].empty or between(data["events"], start, end).empty:
    st.info("No events for this selection. Load the seed scenario or choose January–March 2025.")
    st.stop()
events, users = data["events"], data["users"]
days = pd.date_range(start, end, freq="D", inclusive="left")
activity = engagement(events, days)
current_requests = between(data["requests"], start, end)
f = funnel(users, events, start, end)
rel = reliability(current_requests)
feature_stats = adoption(events, start, end)
st.sidebar.caption("Every record is synthetic. Event time is UTC; ingestion time is separate.")

if page == "Executive Overview":
    latest = activity.iloc[-1]
    cols = st.columns(4)
    for col, name in zip(cols[:3], ["dau", "wau", "mau"], strict=True):
        col.metric(name.upper(), int(latest[name]))
    cols[3].metric("DAU / MAU", f"{latest.stickiness:.1%}")
    st.metric("7-day signup activation / eligible cohort", f"{f.iloc[-1].cohort_conversion:.1%}")
    st.metric("API error rate", f"{rel['error_rate']:.2%}")
    st.metric(
        "Returning users in selected window", f"{returning_percentage(events, start, end):.1%}"
    )
    st.plotly_chart(
        px.line(activity[["dau", "wau", "mau"]], title="Distinct active users"), width="stretch"
    )
    daily = data["daily"]
    d = detect(daily.error_rate)
    st.subheader("Important reliability anomalies")
    st.dataframe(d[(d.index >= start) & (d.index < end) & d.anomaly], hide_index=False)
elif page == "Feature Adoption":
    st.dataframe(feature_stats, hide_index=True)
    st.caption("Adoption = feature users / active users; frequency = events / feature users.")
    observed = between(events, start, end)
    observed["date"] = pd.to_datetime(observed.occurred_at, utc=True).dt.normalize()
    usage = observed[observed.name.isin(FEATURES)].groupby(["date", "name"]).size()
    st.plotly_chart(
        px.line(
            usage.rename("events").reset_index(),
            x="date",
            y="events",
            color="name",
            title="Feature event frequency",
        ),
        width="stretch",
    )
    signup = users[["id", "registered_at"]].copy()
    signup["cohort"] = pd.to_datetime(signup.registered_at, utc=True).dt.strftime("%Y-%m")
    cohort = observed.merge(signup, left_on="user_id", right_on="id")
    cohort_adoption = []
    for name, group in cohort.groupby("cohort"):
        for feature in FEATURES:
            cohort_adoption.append(
                dict(
                    cohort=name,
                    feature=feature,
                    adoption=group[group.name == feature].user_id.nunique()
                    / group.user_id.nunique(),
                )
            )
    st.dataframe(pd.DataFrame(cohort_adoption), hide_index=True)
    st.caption(
        "Cohort feature denominator: active members of each registration month in this window."
    )
    retained = retention(between(users, start, end, "registered_at"), events, end)
    if not retained.empty:
        st.plotly_chart(
            px.imshow(
                retained.pivot(index="cohort", columns="week", values="retention"),
                zmin=0,
                zmax=1,
                title="Mature weekly cohort retention",
            ),
            width="stretch",
        )
elif page == "Conversion Funnel":
    st.caption(
        "Same eligible signup cohort at every step; chronological register → login → "
        "dashboard → activate within 7 days. Incomplete signup horizons are excluded."
    )
    st.plotly_chart(px.funnel(f, x="users", y="stage"), width="stretch")
    st.dataframe(f, hide_index=True)
    st.plotly_chart(
        px.line(
            conversion_trend(users, events, start, end),
            x="week",
            y="conversion",
            title="Seven-day activation by signup week",
        ),
        width="stretch",
    )
    span = end - start
    previous = funnel(users, events, start - span, start)
    st.dataframe(
        pd.DataFrame(
            {
                "current": f.set_index("stage").cohort_conversion,
                "prior_equal_window": previous.set_index("stage").cohort_conversion,
            }
        )
    )
    st.caption("Each comparison excludes its own immature signups; absent cohorts display NA.")
elif page == "Reliability":
    endpoint = st.selectbox("Endpoint", ["all"] + [f"/{x}" for x in FEATURES])
    requests = (
        current_requests
        if endpoint == "all"
        else current_requests[current_requests.endpoint == endpoint]
    )
    st.dataframe(pd.Series(reliability(requests), name="Value"))
    daily = data["daily"]
    st.plotly_chart(
        px.line(
            daily.loc[(daily.index >= start) & (daily.index < end)],
            y="requests",
            title="SQL-aggregated all-endpoint request volume",
        ),
        width="stretch",
    )
    failures = requests[requests.status >= 400].groupby("endpoint").size()
    st.plotly_chart(
        px.bar(failures.rename("failures"), title="Endpoint failure count"), width="stretch"
    )
    st.plotly_chart(
        px.histogram(
            requests,
            x="latency_ms",
            color="endpoint",
            log_y=True,
            title="Response latency (milliseconds)",
        ),
        width="stretch",
    )
    incidents = data["incidents"].copy()
    incidents["duration_hours"] = (
        pd.to_datetime(incidents.ended_at, utc=True)
        - pd.to_datetime(incidents.started_at, utc=True)
    ).dt.total_seconds() / 3600
    incidents = incidents[
        (pd.to_datetime(incidents.started_at, utc=True) < end)
        & (pd.to_datetime(incidents.ended_at, utc=True) > start)
    ]
    st.dataframe(incidents, hide_index=True)
    if not incidents.empty:
        st.plotly_chart(
            px.timeline(
                incidents,
                x_start="started_at",
                x_end="ended_at",
                y="id",
                color="endpoint",
                title="Synthetic incident timeline",
            ),
            width="stretch",
        )
else:
    daily = data["daily"]
    metric = st.selectbox("Monitored metric", ["error_rate", "dau", "feature_events"])
    endpoint = st.selectbox("Endpoint evidence filter", ["all"] + [f"/{x}" for x in FEATURES])
    feature = st.selectbox("Feature for event-count monitoring", FEATURES)
    evidence_data = dict(data)
    if endpoint != "all":
        evidence_data["requests"] = data["requests"][data["requests"].endpoint == endpoint]
    if metric == "error_rate" and endpoint != "all":
        requests = evidence_data["requests"].copy()
        requests["day"] = pd.to_datetime(requests.occurred_at, utc=True).dt.normalize()
        values = requests.groupby("day").status.apply(lambda s: (s >= 400).mean())
        values = values.reindex(daily.index)
    elif metric == "error_rate":
        values = daily.error_rate
    elif metric == "dau":
        values = engagement(events, daily.index).dau
    else:
        observed = events[events.name == feature].copy()
        observed["day"] = pd.to_datetime(observed.occurred_at, utc=True).dt.normalize()
        values = observed.groupby("day").size().reindex(daily.index, fill_value=0)
    method = st.selectbox("Detection method", ["zscore", "mad"])
    severity = st.selectbox("Anomaly severity", ["all", "medium", "high"])
    result = detect(values, method, scale_floor=0.005 if metric == "error_rate" else 1.0)
    shown = result[(result.index >= start) & (result.index < end)]
    st.plotly_chart(
        px.line(shown, y=["actual", "baseline"], title=f"{metric}: actual and prior baseline"),
        width="stretch",
    )
    anomalies = shown[shown.anomaly]
    if severity != "all":
        anomalies = anomalies[anomalies.severity == severity]
    st.dataframe(anomalies)
    st.caption("Baseline: previous 14 observed days. Warm-up dates are not classified.")
    # Evaluate error-rate methods against persisted synthetic incident intervals.
    labels = pd.Series(False, index=daily.index)
    for incident in data["incidents"].itertuples():
        labels |= (labels.index >= utc(incident.started_at)) & (
            labels.index < utc(incident.ended_at)
        )
    comparisons = []
    for name in ["zscore", "mad"]:
        candidate = detect(daily.error_rate, name)
        comparisons.append(
            dict(method=name, **evaluate(candidate.anomaly, labels, candidate.baseline.notna()))
        )
    try:
        prediction = isolation(daily[["error_rate", "mean_latency_ms"]])
        eligible = pd.Series(range(len(daily)), index=daily.index) >= 30
        comparisons.append(
            dict(method="isolation_forest", **evaluate(prediction, labels, eligible))
        )
    except ValueError as exc:
        st.info(str(exc))
    st.dataframe(pd.DataFrame(comparisons), hide_index=True)
    st.caption(
        "Evaluation above uses the complete loaded history, all endpoints, selected segment; "
        "each method has its own warm-up eligibility. Labels identify incident days only."
    )
    change = st.date_input(
        "Investigation change date (UTC)", value=pd.Timestamp("2025-03-02").date()
    )
    findings = investigate(evidence_data, change)
    st.write(findings["limitation"])
    st.dataframe(findings["endpoints"], hide_index=True)
    st.dataframe(findings["segments"], hide_index=True)
    st.dataframe(findings["errors"], hide_index=True)
    st.dataframe(findings["releases"], hide_index=True)
    st.dataframe(findings["records"], hide_index=True)
    st.caption(
        "Investigation compares seven days before versus seven days after the change; "
        "history is limited by the selected observation cutoff."
    )
    if page == "AI Analyst":
        st.caption(
            "The optional model selects evidence and approved investigations. "
            "All numerical facts are rendered directly from validated computations."
        )
        task = st.selectbox("Analyst task", TASKS)
        use_llm = st.checkbox("Use optional OpenAI API (requires environment credentials)")
        evidence = dict(findings["evidence"])
        weekly_start = max(start, end - pd.Timedelta(days=7))
        weekly_activity = engagement(events, pd.date_range(weekly_start, end, inclusive="left"))
        evidence["kpi:weekly"] = dict(
            start=str(weekly_start),
            end_exclusive=str(end),
            latest_dau=int(weekly_activity.iloc[-1].dau),
            latest_wau=int(weekly_activity.iloc[-1].wau),
            latest_mau=int(weekly_activity.iloc[-1].mau),
            **reliability(between(data["requests"], weekly_start, end)),
        )
        evidence["kpi:conversion"] = dict(
            eligible=int(f.iloc[-1].eligible), seven_day_activation=f.iloc[-1].cohort_conversion
        )
        if st.button("Generate analyst report") or not use_llm:
            summary = summarize(evidence, task, use_llm)
            st.json(summary)
            st.download_button(
                "Download HTML report", html_report(summary), "product-report.html", "text/html"
            )
            st.download_button(
                "Download evidence JSON",
                json.dumps(safe_evidence(evidence), indent=2),
                "evidence.json",
                "application/json",
            )

with st.expander("Pipeline audit and data quality"):
    st.dataframe(data["runs"], hide_index=True)
    st.dataframe(data["rejections"], hide_index=True)
st.download_button("Export selected-window daily KPIs", activity.to_csv(), "kpis.csv", "text/csv")
