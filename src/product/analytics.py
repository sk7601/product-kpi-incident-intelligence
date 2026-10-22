"""Precisely defined UTC windows, acquisition cohorts and reliability statistics."""

import numpy as np
import pandas as pd

from product.generation import FEATURES


def utc(value) -> pd.Timestamp:
    return pd.to_datetime(value, utc=True)


def between(frame: pd.DataFrame, start, end, column: str = "occurred_at") -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    times = pd.to_datetime(frame[column], utc=True)
    return frame[(times >= utc(start)) & (times < utc(end))].copy()


def engagement(events: pd.DataFrame, days: pd.DatetimeIndex) -> pd.DataFrame:
    result = []
    stamps = pd.to_datetime(events.occurred_at, utc=True)
    for day in days:
        end = utc(day) + pd.Timedelta(days=1)
        counts = [
            events.loc[(stamps >= end - pd.Timedelta(days=n)) & (stamps < end), "user_id"].nunique()
            for n in [1, 7, 30]
        ]
        result.append(
            dict(
                date=day,
                dau=counts[0],
                wau=counts[1],
                mau=counts[2],
                stickiness=counts[0] / counts[2] if counts[2] else np.nan,
            )
        )
    return pd.DataFrame(result).set_index("date")


def adoption(events: pd.DataFrame, start, end) -> pd.DataFrame:
    active = between(events, start, end)
    denominator = active.user_id.nunique()
    rows = []
    for feature in FEATURES:
        usage = active[active.name == feature]
        users = usage.user_id.nunique()
        rows.append(
            dict(
                feature=feature,
                users=users,
                events=len(usage),
                adoption=users / denominator if denominator else np.nan,
                frequency=len(usage) / users if users else np.nan,
            )
        )
    return pd.DataFrame(rows)


def funnel(
    users: pd.DataFrame, events: pd.DataFrame, start, end, horizon_days: int = 7
) -> pd.DataFrame:
    if horizon_days < 1 or utc(end) <= utc(start):
        raise ValueError("Positive horizon and ordered window required")
    registered = pd.to_datetime(users.registered_at, utc=True)
    eligible = users[
        (registered >= utc(start)) & (registered < utc(end) - pd.Timedelta(days=horizon_days))
    ]
    stages = ["register", "login", "dashboard", "activate"]
    counts = dict.fromkeys(stages, 0)
    event_copy = events.copy()
    event_copy["occurred_at"] = pd.to_datetime(event_copy.occurred_at, utc=True)
    grouped = {
        uid: group.sort_values("occurred_at") for uid, group in event_copy.groupby("user_id")
    }
    for user in eligible.itertuples():
        signup = utc(user.registered_at)
        records = grouped.get(user.id, event_copy.iloc[:0])
        records = records[
            (records.occurred_at >= signup)
            & (records.occurred_at < signup + pd.Timedelta(days=horizon_days))
        ]
        previous = signup - pd.Timedelta(nanoseconds=1)
        for stage in stages:
            found = records[(records.name == stage) & (records.occurred_at > previous)]
            if found.empty:
                break
            counts[stage] += 1
            previous = found.occurred_at.min()
    rows = []
    denominator = len(eligible)
    prior = denominator
    for stage in stages:
        value = counts[stage]
        rows.append(
            dict(
                stage=stage,
                users=value,
                eligible=denominator,
                cohort_conversion=value / denominator if denominator else np.nan,
                stage_conversion=value / prior if prior else np.nan,
                drop_off=1 - value / prior if prior else np.nan,
            )
        )
        prior = value
    return pd.DataFrame(rows)


def conversion_trend(users: pd.DataFrame, events: pd.DataFrame, start, end) -> pd.DataFrame:
    rows = []
    for week in pd.date_range(utc(start).normalize(), utc(end), freq="7D", inclusive="left"):
        cohort_end = min(week + pd.Timedelta(days=7), utc(end))
        # Eligibility must be based on the observation cutoff, not the cohort end.
        subset = users[
            (pd.to_datetime(users.registered_at, utc=True) >= week)
            & (pd.to_datetime(users.registered_at, utc=True) < cohort_end)
        ]
        f = funnel(subset, events, week, end)
        rows.append(
            dict(
                week=week,
                conversion=f.iloc[-1].cohort_conversion,
                eligible=int(f.iloc[-1].eligible),
            )
        )
    return pd.DataFrame(rows)


def retention(users: pd.DataFrame, events: pd.DataFrame, end) -> pd.DataFrame:
    if users.empty:
        return pd.DataFrame(columns=["cohort", "week", "users", "cohort_size", "retention"])
    u = users.copy()
    signup = pd.to_datetime(u.registered_at, utc=True).dt.normalize()
    u["cohort"] = signup - pd.to_timedelta(signup.dt.weekday, unit="D")
    observed = events.copy()
    observed["occurred_at"] = pd.to_datetime(observed.occurred_at, utc=True)
    rows = []
    for cohort, group in u.groupby("cohort"):
        for week in range(max(0, int((utc(end) - cohort).days // 7))):
            begin = cohort + pd.Timedelta(days=7 * week)
            finish = begin + pd.Timedelta(days=7)
            if finish > utc(end):
                continue
            active = observed[
                (observed.occurred_at >= begin)
                & (observed.occurred_at < finish)
                & observed.user_id.isin(group.id)
            ].user_id.nunique()
            rows.append(
                dict(
                    cohort=str(cohort.date()),
                    week=week,
                    users=active,
                    cohort_size=len(group),
                    retention=active / len(group),
                )
            )
    return pd.DataFrame(rows)


def returning_percentage(events: pd.DataFrame, start, end) -> float:
    current = set(between(events, start, end).user_id)
    prior = set(events.loc[pd.to_datetime(events.occurred_at, utc=True) < utc(start), "user_id"])
    return len(current & prior) / len(current) if current else np.nan


def reliability(requests: pd.DataFrame) -> dict:
    if requests.empty:
        return dict(requests=0, errors=0, error_rate=np.nan, p50=np.nan, p95=np.nan, p99=np.nan)
    failed = int((requests.status >= 400).sum())
    return dict(
        requests=len(requests),
        errors=failed,
        error_rate=failed / len(requests),
        **{f"p{q}": float(requests.latency_ms.quantile(q / 100)) for q in [50, 95, 99]},
    )
