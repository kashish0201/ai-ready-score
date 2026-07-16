import pandas as pd
import pytest

from backend.quality import (
    compute_ai_ready_score,
    get_dataset_overview,
    run_quality_checks,
)


def test_get_dataset_overview_counts():
    df = pd.DataFrame({"a": [1, 2], "b": ["x", None]})
    overview = get_dataset_overview(df)
    assert overview["rows"] == 2
    assert overview["columns"] == 2
    assert overview["missing_pct"] == pytest.approx(25.0)
    assert overview["numeric_columns"] == 1
    assert overview["categorical_columns"] == 1


def test_class_imbalance_detected():
    df = pd.DataFrame({"x": range(20), "y": [0] * 18 + [1] * 2})
    issues = run_quality_checks(df, target_col="y")
    assert (issues["check"] == "class_imbalance").any()


def test_no_imbalance_when_balanced():
    df = pd.DataFrame({"x": range(10), "y": [0] * 5 + [1] * 5})
    issues = run_quality_checks(df, target_col="y")
    if len(issues) == 0:
        assert True
    else:
        assert not (issues["check"] == "class_imbalance").any()


def test_compute_ai_ready_score_empty():
    result = compute_ai_ready_score(pd.DataFrame(columns=[
        "check", "column", "severity", "metric", "value",
        "explanation", "recommendation",
    ]))
    assert result["score"] == 100
    assert result["grade"] == "Excellent"
