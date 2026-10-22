import numpy as np
import pandas as pd
import pytest

from product.detection import detect, evaluate, isolation


@pytest.mark.parametrize("method", ["zscore", "mad"])
def test_constant_baseline_and_no_leakage(method):
    values = pd.Series([0.01] * 20 + [0.3] + [0.01] * 5)
    d = detect(values, method)
    assert d.baseline.iloc[:14].isna().all()
    assert d.iloc[20].baseline == pytest.approx(0.01)
    assert d.iloc[20].anomaly
    assert not d.anomaly.iloc[:20].any()
    labels = pd.Series([False] * 20 + [True] + [False] * 5)
    result = evaluate(d.anomaly, labels, d.baseline.notna())
    assert result["recall"] == 1 and result["false_positives"] == 0


def test_detection_edges():
    for args in [dict(method="bad"), dict(window=1), dict(scale_floor=0)]:
        with pytest.raises(ValueError):
            detect(pd.Series([1, 2]), **args)
    with pytest.raises(ValueError):
        isolation(pd.DataFrame({"x": [1, 2]}))
    with pytest.raises(ValueError):
        isolation(pd.DataFrame({"x": [np.nan] * 40}))
    frame = pd.DataFrame(
        {
            "error_rate": list(np.linspace(0.005, 0.025, 35)) + [0.9] * 5,
            "latency": list(np.linspace(90, 130, 35)) + [1000] * 5,
        }
    )
    out = isolation(frame)
    assert not out.iloc[:30].any() and out.iloc[-5:].all()


def test_isolation_constant_baseline():
    with pytest.raises(ValueError, match="variation"):
        isolation(pd.DataFrame({"x": [1] * 40}))
