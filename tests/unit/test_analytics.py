import numpy as np
import pandas as pd
import pytest

from product.analytics import (
    adoption,
    conversion_trend,
    engagement,
    funnel,
    reliability,
    retention,
    returning_percentage,
)


def fixture():
    users = pd.DataFrame(
        [
            dict(id="a", registered_at="2025-01-01T00:00:00Z"),
            dict(id="b", registered_at="2025-01-01T00:00:00Z"),
            dict(id="c", registered_at="2025-01-19T00:00:00Z"),
        ]
    )
    rows = []
    for uid, actions in [
        ("a", ["register", "login", "dashboard", "activate"]),
        ("b", ["register", "dashboard", "login"]),
    ]:
        for hour, name in enumerate(actions):
            rows.append(dict(user_id=uid, name=name, occurred_at=f"2025-01-01T0{hour}:00:00Z"))
    rows.append(dict(user_id="a", name="search", occurred_at="2025-01-08T01:00:00Z"))
    return users, pd.DataFrame(rows)


def test_ordered_funnel_denominator():
    users, events = fixture()
    f = funnel(users, events, "2025-01-01", "2025-01-20")
    assert f.users.tolist() == [2, 2, 1, 1]
    assert f.eligible.tolist() == [2] * 4
    assert f.iloc[-1].cohort_conversion == 0.5
    assert f.iloc[2].drop_off == 0.5
    empty = funnel(users, events, "2025-02-01", "2025-02-20")
    assert empty.cohort_conversion.isna().all()
    with pytest.raises(ValueError):
        funnel(users, events, "2025-02-20", "2025-01-20")
    trend = conversion_trend(users, events, "2025-01-01", "2025-01-20")
    assert trend.iloc[0].conversion == 0.5


def test_engagement_adoption_and_returning():
    _, events = fixture()
    days = pd.date_range("2025-01-01", "2025-01-08", tz="UTC")
    e = engagement(events, days)
    assert e.iloc[0].dau == 2 and e.iloc[-1].dau == 1
    assert e.iloc[-1].wau == 1 and e.iloc[-1].mau == 2
    assert e.iloc[-1].stickiness == 0.5
    a = adoption(events, "2025-01-01", "2025-01-09").set_index("feature")
    assert a.loc["search", "adoption"] == 0.5
    assert a.loc["dashboard", "frequency"] == 1
    assert returning_percentage(events, "2025-01-08", "2025-01-09") == 1
    assert np.isnan(returning_percentage(events, "2025-02-01", "2025-02-02"))


def test_retention_maturity():
    users, events = fixture()
    r = retention(users, events, "2025-01-12").set_index(["cohort", "week"])
    assert r.loc[("2024-12-30", 0), "retention"] == 1
    # Jan 6-12 is incomplete at Jan 12 00:00; omit it entirely.
    assert ("2024-12-30", 1) not in r.index
    r = retention(users.iloc[:2], events, "2025-01-13").set_index(["cohort", "week"])
    assert r.loc[("2024-12-30", 1), "retention"] == 0.5
    assert retention(users.iloc[:0], events, "2025-01-13").empty


def test_reliability():
    requests = pd.DataFrame(dict(status=[200, 200, 500, 504], latency_ms=[10, 20, 30, 40]))
    result = reliability(requests)
    assert result["error_rate"] == 0.5
    assert result["p50"] == 25
    assert result["p95"] == pytest.approx(38.5)
    assert result["p99"] == pytest.approx(39.7)
    assert np.isnan(reliability(requests.iloc[:0])["error_rate"])
