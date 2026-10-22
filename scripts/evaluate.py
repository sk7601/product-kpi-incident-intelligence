"""Reproduce detector measurements from persisted synthetic incident labels."""

import argparse
import json

import pandas as pd

from product.analytics import utc
from product.detection import detect, evaluate, isolation
from product.services import load


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--end", default="2025-04-01")
    args = parser.parse_args()
    data = load(args.end)
    daily = data["daily"]
    if daily.empty:
        raise ValueError("Load the synthetic scenario before evaluating")
    labels = pd.Series(False, index=daily.index)
    for incident in data["incidents"].itertuples():
        labels |= (labels.index >= utc(incident.started_at)) & (
            labels.index < utc(incident.ended_at)
        )
    rows = []
    for method in ["zscore", "mad"]:
        result = detect(daily.error_rate, method)
        rows.append(
            dict(method=method, **evaluate(result.anomaly, labels, result.baseline.notna()))
        )
    prediction = isolation(daily[["error_rate", "mean_latency_ms"]])
    eligible = pd.Series(range(len(daily)), index=daily.index) >= 30
    rows.append(dict(method="isolation_forest", **evaluate(prediction, labels, eligible)))
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
