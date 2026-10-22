from copy import deepcopy
from datetime import datetime, timezone

import pytest

from product.generation import generate
from product.validation import timestamp, validate_bundle


def test_generator_and_clean_pipeline():
    data = generate(days=3)
    assert data == generate(days=3)
    clean, errors = validate_bundle(data)
    assert not errors
    assert len(clean["events"]) > 0
    with pytest.raises(ValueError):
        generate(days=100)


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("id", None, "Missing"),
        ("id", 7, "Invalid ID"),
        ("user_id", "ghost", "Unknown user"),
        ("session_id", "ghost", "session reference"),
        ("name", "hack", "Unknown event"),
        ("occurred_at", "bad", "Invalid isoformat"),
        ("occurred_at", "2025-01-01T00:00:00", "timezone"),
        ("occurred_at", "2024-01-01T00:00:00+00:00", "predates"),
        ("occurred_at", "2025-01-01T23:59:59+00:00", "outside session"),
        ("properties", [], "Properties"),
    ],
)
def test_event_defects(field, value, match):
    data = generate(days=1)
    data["events"][0][field] = value
    _, errors = validate_bundle(data)
    assert any(match in r["reason"] for r in errors)


def test_duplicates_transitions_and_null_properties():
    data = generate(days=1)
    data["events"].append(deepcopy(data["events"][0]))
    _, errors = validate_bundle(data)
    assert any("Duplicate ID" in r["reason"] for r in errors)
    data = generate(days=1)
    first = data["events"][0]
    first["name"] = "activate"
    _, errors = validate_bundle(data)
    assert any("before login" in r["reason"] for r in errors)
    data = generate(days=1)
    data["events"][0]["properties"] = None
    clean, _ = validate_bundle(data)
    assert (
        next(r for r in clean["events"] if r["id"] == data["events"][0]["id"])["properties"] == {}
    )


@pytest.mark.parametrize(
    "table,field,value,match",
    [
        ("users", "segment", "bad", "segment"),
        ("sessions", "ended_at", "2024-01-01T00:00:00+00:00", "End precedes"),
        ("requests", "status", 999, "status"),
        ("requests", "latency_ms", -1, "latency"),
        ("requests", "latency_ms", "nan", "latency"),
        ("requests", "release_id", "v3", "release"),
        ("requests", "endpoint", "/unknown", "endpoint"),
    ],
)
def test_other_records(table, field, value, match):
    data = generate(days=3)
    data[table][0][field] = value
    _, errors = validate_bundle(data)
    assert any(match in r["reason"] for r in errors)


def test_future_timestamp():
    with pytest.raises(ValueError, match="Future"):
        timestamp(datetime(2999, 1, 1, tzinfo=timezone.utc))


def test_extra_fields_and_non_json_properties():
    data = generate(days=1)
    data["events"][0]["unexpected"] = "field"
    _, errors = validate_bundle(data)
    assert any("schema fields" in r["reason"] for r in errors)
    data = generate(days=1)
    data["events"][0]["properties"] = {"bad": float("nan")}
    _, errors = validate_bundle(data)
    assert any(r["table_name"] == "events" for r in errors)


def test_error_references_and_activation_order():
    data = generate(days=3)
    data["errors"].append(dict(id="bad-error", request_id="unknown", error_type="Timeout"))
    _, errors = validate_bundle(data)
    assert any("failing request" in r["reason"] for r in errors)
    data = generate(days=3)
    for event in data["events"]:
        if event["name"] == "dashboard":
            event["name"] = "search"
    _, errors = validate_bundle(data)
    assert any("before dashboard" in r["reason"] for r in errors)
