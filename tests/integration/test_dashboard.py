from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from product.database import Base, engine
from product.generation import generate
from product.pipeline import ingest


@pytest.fixture(scope="module")
def demo_url(tmp_path_factory):
    url = f"sqlite:///{tmp_path_factory.mktemp('ui') / 'product.db'}"
    Base.metadata.create_all(engine(url))
    ingest(generate(), url)
    return url


@pytest.mark.parametrize(
    "page",
    [
        "Executive Overview",
        "Feature Adoption",
        "Conversion Funnel",
        "Reliability",
        "Anomaly Investigation",
        "AI Analyst",
    ],
)
def test_pages(page, demo_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", demo_url)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file(str(Path(__file__).parents[2] / "app/dashboard.py"))
    app.run(timeout=40)
    app.sidebar.radio[0].set_value(page).run(timeout=40)
    assert not app.exception
    assert not app.error
    if page == "AI Analyst":
        assert len(app.json) >= 1


def test_empty_and_segment_filters(demo_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", demo_url)
    app = AppTest.from_file(str(Path(__file__).parents[2] / "app/dashboard.py"))
    app.run(timeout=40)
    app.sidebar.selectbox[0].set_value("enterprise").run(timeout=40)
    assert not app.exception
    app.sidebar.date_input[0].set_value(("2026-01-01", "2026-01-10")).run(timeout=40)
    assert not app.exception
    assert app.info


def test_investigation_controls(demo_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", demo_url)
    app = AppTest.from_file(str(Path(__file__).parents[2] / "app/dashboard.py"))
    app.run(timeout=40)
    app.sidebar.radio[0].set_value("Anomaly Investigation").run(timeout=40)
    for metric in ["dau", "feature_events"]:
        next(x for x in app.selectbox if x.label == "Monitored metric").set_value(metric)
        app.run(timeout=40)
        assert not app.exception
    next(x for x in app.selectbox if x.label == "Endpoint evidence filter").set_value("/report")
    next(x for x in app.selectbox if x.label == "Detection method").set_value("mad")
    next(x for x in app.selectbox if x.label == "Anomaly severity").set_value("high")
    app.run(timeout=40)
    assert not app.exception
