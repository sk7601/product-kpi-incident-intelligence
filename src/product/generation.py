"""Seeded entirely synthetic 90-day SaaS scenario, never real customers."""

from datetime import datetime, timedelta, timezone

import numpy as np

START = datetime(2025, 1, 1, tzinfo=timezone.utc)
END = START + timedelta(days=90)
FEATURES = ["dashboard", "search", "report", "export"]
EVENTS = ["register", "login", *FEATURES, "activate"]


def generate(seed: int = 42, days: int = 90) -> dict[str, list[dict]]:
    if not 1 <= days <= 90:
        raise ValueError("Scenario supports 1 to 90 days")
    rng = np.random.default_rng(seed)
    data = {
        k: []
        for k in ["users", "sessions", "events", "requests", "errors", "releases", "incidents"]
    }
    data["releases"] = [
        dict(id="v1", deployed_at=START, description="Synthetic baseline"),
        dict(
            id="v2",
            deployed_at=START + timedelta(days=60),
            description="Synthetic report-service release",
        ),
        dict(
            id="v3",
            deployed_at=START + timedelta(days=67),
            description="Synthetic recovery release",
        ),
    ]
    data["incidents"] = [
        dict(
            id="INC-SYN-1",
            started_at=START + timedelta(days=60),
            ended_at=START + timedelta(days=67),
            endpoint="/report",
            description="Labeled synthetic report timeout window; not a causal finding",
        )
    ]
    event_id = request_id = 0
    for day in range(days):
        base = START + timedelta(days=day, hours=9)
        new_users = []
        for _ in range(3 + day // 30):
            user = dict(
                id=f"u{len(data['users']):04}",
                registered_at=base,
                segment=str(rng.choice(["starter", "enterprise"], p=[0.7, 0.3])),
            )
            data["users"].append(user)
            new_users.append(user["id"])
        incident = 60 <= day < 67
        for user in data["users"]:
            new = user["id"] in new_users
            if not new and rng.random() > 0.13 + day * 0.0005:
                continue
            sid = f"s{len(data['sessions']):06}"
            begin = base + timedelta(minutes=int(rng.integers(0, 300)))
            data["sessions"].append(
                dict(
                    id=sid,
                    user_id=user["id"],
                    started_at=begin,
                    ended_at=begin + timedelta(minutes=40),
                )
            )
            actions = (["register"] if new else []) + ["login", "dashboard"]
            if rng.random() < 0.8:
                actions.append("search")
            if rng.random() < 0.65:
                actions.append("report")
            # Declining export engagement despite growing population.
            if rng.random() < 0.65 - 0.005 * day:
                actions.append("export")
            if new and rng.random() < (0.12 if incident else 0.58):
                actions.append("activate")
            for minute, name in enumerate(actions):
                stamp = begin + timedelta(minutes=minute)
                eid = f"e{event_id:07}"
                event_id += 1
                data["events"].append(
                    dict(
                        id=eid,
                        user_id=user["id"],
                        session_id=sid,
                        name=name,
                        occurred_at=stamp,
                        properties={"synthetic": True},
                    )
                )
                if name not in FEATURES:
                    continue
                for _ in range(3):
                    rid = f"r{request_id:07}"
                    request_id += 1
                    failure = rng.random() < (0.8 if incident and name == "report" else 0.015)
                    data["requests"].append(
                        dict(
                            id=rid,
                            user_id=user["id"],
                            session_id=sid,
                            occurred_at=stamp,
                            endpoint=f"/{name}",
                            status=504 if failure else 200,
                            latency_ms=round(
                                float(rng.lognormal(5.1 if not failure else 7.5, 0.3)), 2
                            ),
                            release_id="v1" if day < 60 else "v2" if day < 67 else "v3",
                        )
                    )
                    if failure:
                        data["errors"].append(
                            dict(id=f"err-{rid}", request_id=rid, error_type="Timeout")
                        )
    return data
