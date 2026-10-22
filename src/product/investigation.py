"""Evidence comparisons establish association, not causation."""

import pandas as pd

from product.analytics import between, reliability, utc


def investigate(data: dict, change_date, days: int = 7) -> dict:
    if days < 1:
        raise ValueError("Positive comparison window required")
    change = utc(change_date)
    before = between(data["requests"], change - pd.Timedelta(days=days), change)
    after = between(data["requests"], change, change + pd.Timedelta(days=days))
    evidence = {}
    endpoints = []
    for endpoint in sorted(set(before.endpoint) | set(after.endpoint)):
        a = reliability(before[before.endpoint == endpoint])
        b = reliability(after[after.endpoint == endpoint])
        key = f"endpoint:{endpoint}"
        evidence[key] = dict(
            endpoint=endpoint,
            before=a,
            after=b,
            sample_request_ids=after[(after.endpoint == endpoint) & (after.status >= 400)]
            .id.head(5)
            .tolist(),
        )
        endpoints.append(
            dict(
                endpoint=endpoint,
                before_rate=a["error_rate"],
                after_rate=b["error_rate"],
                requests=b["requests"],
                evidence_id=key,
            )
        )
    segment_rows = []
    for segment in sorted(set(after.segment)):
        stats = reliability(after[after.segment == segment])
        key = f"segment:{segment}"
        evidence[key] = dict(segment=segment, **stats)
        segment_rows.append(dict(segment=segment, **stats, evidence_id=key))
    releases = data["releases"].copy()
    deployed = pd.to_datetime(releases.deployed_at, utc=True)
    nearby = releases[
        (deployed >= change - pd.Timedelta(days=3)) & (deployed < change + pd.Timedelta(days=3))
    ]
    for release in nearby.itertuples():
        evidence[f"release:{release.id}"] = dict(
            id=release.id, deployed_at=str(release.deployed_at)
        )
    records = after[after.status >= 400].head(100)
    joined = data["errors"].merge(after[["id", "endpoint"]], left_on="request_id", right_on="id")
    error_counts = joined.groupby(["endpoint", "error_type"]).size().rename("count").reset_index()
    for row in error_counts.itertuples():
        evidence[f"error:{row.endpoint}:{row.error_type}"] = dict(count=int(row.count))
    return dict(
        change_date=str(change),
        before=reliability(before),
        after=reliability(after),
        endpoints=pd.DataFrame(endpoints),
        segments=pd.DataFrame(segment_rows),
        releases=nearby,
        errors=error_counts,
        records=records,
        evidence=evidence,
        limitation="Temporal association does not establish release causation. Check traffic mix, "
        "dependencies, deployment rollback evidence and controlled comparisons.",
    )
