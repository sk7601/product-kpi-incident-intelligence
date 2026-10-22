"""Past-only baselines; explicit warm-up and zero-variance behavior."""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score


def detect(
    values: pd.Series,
    method: str = "zscore",
    window: int = 14,
    threshold: float = 3.0,
    scale_floor: float = 0.005,
) -> pd.DataFrame:
    if method not in {"zscore", "mad"} or window < 3 or threshold <= 0 or scale_floor <= 0:
        raise ValueError("Invalid detector configuration")
    values = values.astype(float)
    prior = values.shift(1).rolling(window, min_periods=window)
    baseline = prior.mean() if method == "zscore" else prior.median()
    scale = (
        prior.std(ddof=1)
        if method == "zscore"
        else prior.apply(lambda x: 1.4826 * np.median(np.abs(x - np.median(x))), raw=True)
    )
    # Floor prevents divide-by-zero without calling tiny fluctuations enormous signals.
    score = (values - baseline) / scale.clip(lower=scale_floor)
    return pd.DataFrame(
        dict(
            actual=values,
            baseline=baseline,
            deviation=values - baseline,
            score=score,
            anomaly=score.abs().gt(threshold),
            severity=np.where(score.abs() > threshold * 2, "high", "medium"),
        )
    )


def isolation(features: pd.DataFrame, baseline_rows: int = 30) -> pd.Series:
    if baseline_rows < 10 or len(features) <= baseline_rows:
        raise ValueError("Need baseline of 10+ rows and later observations")
    if not np.isfinite(features.to_numpy()).all():
        raise ValueError("Finite complete feature matrix required")
    if features.iloc[:baseline_rows].nunique().le(1).all():
        raise ValueError("Isolation Forest requires variation in baseline features")
    model = IsolationForest(n_estimators=150, contamination=0.05, random_state=42)
    model.fit(features.iloc[:baseline_rows])
    result = pd.Series(False, index=features.index)
    result.iloc[baseline_rows:] = model.predict(features.iloc[baseline_rows:]) == -1
    return result


def evaluate(predicted: pd.Series, labels: pd.Series, eligible: pd.Series | None = None) -> dict:
    predicted, labels = predicted.align(labels, join="inner")
    if eligible is not None:
        mask = eligible.reindex(predicted.index).fillna(False)
        predicted, labels = predicted[mask], labels[mask]
    return dict(
        precision=float(precision_score(labels, predicted, zero_division=0)),
        recall=float(recall_score(labels, predicted, zero_division=0)),
        false_positives=int((predicted & ~labels).sum()),
        evaluated_days=len(predicted),
        labeled_days=int(labels.sum()),
    )
