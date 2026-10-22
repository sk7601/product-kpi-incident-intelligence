"""Strict raw-record validation with rejection evidence and reference checks."""

import json
import math
from datetime import datetime

from product.database import utcnow
from product.generation import EVENTS, FEATURES


def timestamp(value) -> datetime:
    result = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Timestamps require explicit timezone")
    if result > utcnow():
        raise ValueError("Future timestamp")
    return result


FIELDS = {
    "users": {"id", "registered_at", "segment"},
    "sessions": {"id", "user_id", "started_at", "ended_at"},
    "events": {"id", "user_id", "session_id", "name", "occurred_at"},
    "requests": {
        "id",
        "user_id",
        "session_id",
        "occurred_at",
        "endpoint",
        "status",
        "latency_ms",
        "release_id",
    },
    "errors": {"id", "request_id", "error_type"},
    "releases": {"id", "deployed_at", "description"},
    "incidents": {"id", "started_at", "ended_at", "endpoint", "description"},
}
ORDER = ["users", "releases", "incidents", "sessions", "events", "requests", "errors"]


def validate_bundle(data: dict) -> tuple[dict, list[dict]]:
    clean = {table: [] for table in ORDER}
    rejected = []
    lookup = {table: {} for table in ORDER}
    state: dict[str, set[str]] = {}
    for table in ORDER:
        records = data.get(table, [])
        if table == "events":
            records = sorted(records, key=lambda r: str(r.get("occurred_at", "")))
        seen = set()
        for original in records:
            row = dict(original)
            try:
                if set(row) - (FIELDS[table] | ({"properties"} if table == "events" else set())):
                    raise ValueError("Unexpected schema fields")
                if not FIELDS[table] <= row.keys() or any(row[k] is None for k in FIELDS[table]):
                    raise ValueError("Missing required field")
                if not isinstance(row["id"], str) or not row["id"] or len(row["id"]) > 50:
                    raise ValueError("Invalid ID")
                if row["id"] in seen:
                    raise ValueError("Duplicate ID")
                seen.add(row["id"])
                for key in list(row):
                    if key.endswith("_at"):
                        row[key] = timestamp(row[key])
                if table == "users" and row["segment"] not in {"starter", "enterprise"}:
                    raise ValueError("Unsupported segment")
                if table in {"sessions", "events", "requests"}:
                    user = lookup["users"].get(row["user_id"])
                    if not user:
                        raise ValueError("Unknown user")
                    occurred = row.get("occurred_at", row.get("started_at"))
                    if occurred < user["registered_at"]:
                        raise ValueError("Record predates registration")
                if table in {"sessions", "incidents"} and row["ended_at"] < row["started_at"]:
                    raise ValueError("End precedes start")
                if table in {"events", "requests"}:
                    session = lookup["sessions"].get(row["session_id"])
                    if not session or session["user_id"] != row["user_id"]:
                        raise ValueError("Invalid session reference")
                    if not session["started_at"] <= row["occurred_at"] <= session["ended_at"]:
                        raise ValueError("Occurrence outside session")
                if table == "events":
                    if row["name"] not in EVENTS:
                        raise ValueError("Unknown event")
                    row["properties"] = {} if row.get("properties") is None else row["properties"]
                    if not isinstance(row["properties"], dict):
                        raise ValueError("Properties must be an object")
                    json.dumps(row["properties"], allow_nan=False)
                    previous = state.setdefault(row["session_id"], set())
                    if row["name"] in FEATURES + ["activate"] and "login" not in previous:
                        raise ValueError("Feature before login")
                    if row["name"] == "activate" and "dashboard" not in previous:
                        raise ValueError("Activation before dashboard")
                    previous.add(row["name"])
                if table == "requests":
                    if not isinstance(row["status"], int) or not 100 <= row["status"] <= 599:
                        raise ValueError("Invalid HTTP status")
                    row["latency_ms"] = float(row["latency_ms"])
                    if not math.isfinite(row["latency_ms"]) or row["latency_ms"] < 0:
                        raise ValueError("Invalid latency")
                    if row["endpoint"] not in {f"/{f}" for f in FEATURES}:
                        raise ValueError("Unsupported endpoint")
                    release = lookup["releases"].get(row["release_id"])
                    if not release or release["deployed_at"] > row["occurred_at"]:
                        raise ValueError("Invalid release reference")
                if table == "errors":
                    request = lookup["requests"].get(row["request_id"])
                    if not request or request["status"] < 400:
                        raise ValueError("Error needs a failing request")
                    if any(r["request_id"] == row["request_id"] for r in clean["errors"]):
                        raise ValueError("Duplicate error request")
                clean[table].append(row)
                lookup[table][row["id"]] = row
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                rejected.append(
                    dict(
                        table_name=table,
                        record_id=str(original.get("id", "")),
                        reason=str(exc),
                        raw={str(k): str(v) for k, v in original.items()},
                    )
                )
    return clean, rejected
