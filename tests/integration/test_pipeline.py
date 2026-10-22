import os

import pandas as pd
import pytest
from sqlalchemy import func, select

from product.database import Base, Event, Rejection, Run, engine, sessions
from product.detection import detect, evaluate
from product.generation import generate
from product.investigation import investigate
from product.pipeline import ingest
from product.services import load


@pytest.fixture
def url(tmp_path, monkeypatch):
    value = os.getenv("TEST_DATABASE_URL", f"sqlite:///{tmp_path / 'product.db'}")
    monkeypatch.setenv("DATABASE_URL", value)
    db = engine(value)
    Base.metadata.drop_all(db)
    Base.metadata.create_all(db)
    yield value
    Base.metadata.drop_all(db)
    db.dispose()


def test_idempotent_audit_and_rejections(url):
    data = generate(days=5)
    ingest(data, url)
    ingest(data, url)
    with sessions(url)() as db:
        assert db.scalar(select(func.count()).select_from(Event)) == len(data["events"])
        assert db.scalar(select(func.count()).select_from(Run)) == 2
    data["events"].append(data["events"][0].copy())
    run_id = ingest(data, url)
    with sessions(url)() as db:
        assert db.get(Run, run_id).rejected == 1
        assert db.scalar(select(func.count()).select_from(Rejection)) == 1
    with pytest.raises(AttributeError):
        ingest({"events": [None]}, url)
    with sessions(url)() as db:
        assert db.scalars(select(Run).order_by(Run.id.desc())).first().status == "failed"


def test_incident_detection_and_evidence(url):
    ingest(generate(), url)
    data = load("2025-04-01")
    assert data["daily"].index.nunique() == 90
    labels = pd.Series(
        (data["daily"].index >= pd.Timestamp("2025-03-02", tz="UTC"))
        & (data["daily"].index < pd.Timestamp("2025-03-09", tz="UTC")),
        index=data["daily"].index,
    )
    for method in ["zscore", "mad"]:
        d = detect(data["daily"].error_rate, method)
        score = evaluate(d.anomaly, labels, d.baseline.notna())
        assert d.loc[pd.Timestamp("2025-03-02", tz="UTC"), "anomaly"]
        assert score["recall"] > 0
        assert score["labeled_days"] == 7
    investigation = investigate(data, "2025-03-02")
    endpoint = investigation["endpoints"].set_index("endpoint").loc["/report"]
    assert endpoint.after_rate > endpoint.before_rate + 0.5
    assert "release:v2" in investigation["evidence"]
    assert not investigation["records"].empty
    assert not investigation["errors"].empty
    with pytest.raises(ValueError):
        investigate(data, "2025-03-02", 0)
