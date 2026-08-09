"""Tests for semantic tag proposals and fix-guard behavior."""

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app
from backend.fixes import fix_missing_values, fix_numeric_outliers
from semantic_tags import propose_tags

client = TestClient(app)


def divvy_like(n=200, seed=0):
    """Small frame shaped like Divvy trip data for tag / outlier tests."""
    rng = np.random.default_rng(seed)
    # Clustered Chicago coords + strong extremes so IQR capping shifts the mean.
    core = n - 20
    lat = np.concatenate([
        rng.normal(41.88, 0.01, core),
        np.full(10, 41.88),
        np.full(5, -80.0),
        np.full(5, 85.0),
    ])
    lng = np.concatenate([
        rng.normal(-87.65, 0.01, core),
        np.full(10, -87.65),
        np.full(5, -170.0),
        np.full(5, 170.0),
    ])
    # Repeat timestamps so uniqueness < 0.95 (otherwise identifier wins over temporal).
    stamp_pool = [f"2021-12-{(i % 12) + 1:02d} 12:00:00" for i in range(12)]
    return pd.DataFrame({
        "ride_id": [f"R{i:06d}" for i in range(n)],
        "started_at": [stamp_pool[i % len(stamp_pool)] for i in range(n)],
        "ended_at": [stamp_pool[(i + 1) % len(stamp_pool)] for i in range(n)],
        "start_lat": lat,
        "start_lng": lng,
        "end_lat": lat + rng.normal(0, 0.005, n),
        "end_lng": lng + rng.normal(0, 0.005, n),
        "start_station_name": rng.choice(
            ["Kingsbury St & Kinzie St", "Canal St & Adams St", "Wells St"],
            size=n,
        ),
        "start_station_id": rng.choice(["KA1503000043", "13050", "TA1308000043"], size=n),
        "member_casual": rng.choice(["member", "casual"], size=n, p=[0.7, 0.3]),
        "extra_num": np.concatenate([
            rng.normal(100, 5, n - 5),
            np.array([10_000, 12_000, -5_000, 15_000, 20_000]),
        ]),
    })


def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def upload(df: pd.DataFrame) -> str:
    files = {"file": ("divvy.csv", csv_bytes(df), "text/csv")}
    res = client.post("/api/datasets", files=files)
    assert res.status_code == 200, res.text
    return res.json()["dataset_id"]


def test_propose_tags_divvy_like_columns():
    df = divvy_like()
    proposed = propose_tags(df)

    assert proposed["start_lat"]["tag"] == "geographic"
    assert proposed["start_lng"]["tag"] == "geographic"
    assert proposed["end_lat"]["tag"] == "geographic"
    assert proposed["end_lng"]["tag"] == "geographic"
    assert proposed["start_lat"]["confidence"] == "high"

    assert proposed["ride_id"]["tag"] == "identifier"
    assert proposed["ride_id"]["confidence"] == "high"

    assert proposed["started_at"]["tag"] == "temporal"
    assert proposed["ended_at"]["tag"] == "temporal"

    # Correctly untagged — no strong solitary evidence
    assert "start_station_name" not in proposed
    assert "start_station_id" not in proposed
    assert "member_casual" not in proposed


def test_numeric_outliers_skips_geographic_when_tagged():
    df = divvy_like()
    tags = {
        "start_lat": "geographic",
        "start_lng": "geographic",
        "end_lat": "geographic",
        "end_lng": "geographic",
    }

    _, log_plain = fix_numeric_outliers(df)
    capped_plain = {c["column"] for c in log_plain["columns_capped"]}
    assert "start_lat" in capped_plain or "start_lng" in capped_plain

    _, log_tagged = fix_numeric_outliers(df, tags=tags)
    capped_tagged = {c["column"] for c in log_tagged["columns_capped"]}
    skipped = {s["column"] for s in log_tagged["skipped"]}

    assert "start_lat" not in capped_tagged
    assert "start_lng" not in capped_tagged
    assert "end_lat" not in capped_tagged
    assert "end_lng" not in capped_tagged
    assert skipped & {"start_lat", "start_lng", "end_lat", "end_lng"}


def test_missing_values_skips_geographic_when_tagged():
    df = divvy_like()
    df.loc[0:9, "end_lat"] = np.nan
    df.loc[0:9, "end_lng"] = np.nan
    tags = {"end_lat": "geographic", "end_lng": "geographic"}

    _, log = fix_missing_values(df, tags=tags)
    imputed = {c["column"] for c in log["columns_imputed"]}
    skipped = {s["column"] for s in log["skipped"]}

    assert "end_lat" not in imputed
    assert "end_lng" not in imputed
    assert "end_lat" in skipped
    assert "end_lng" in skipped


def test_tags_none_matches_untagged_behavior():
    df = divvy_like()
    fixed_a, log_a = fix_numeric_outliers(df, tags=None)
    fixed_b, log_b = fix_numeric_outliers(df)
    pd.testing.assert_frame_equal(fixed_a, fixed_b)
    assert log_a["columns_capped"] == log_b["columns_capped"]


def test_api_tags_preview_protection():
    df = divvy_like()
    dataset_id = upload(df)
    client.put(f"/api/datasets/{dataset_id}/target", json={"target_col": "member_casual"})

    tags_res = client.get(f"/api/datasets/{dataset_id}/tags")
    assert tags_res.status_code == 200
    proposed = tags_res.json()["proposed"]
    assert proposed["ride_id"]["tag"] == "identifier"
    assert proposed["start_lat"]["tag"] == "geographic"
    assert "member_casual" not in proposed

    # Without tags: geo columns are capped (and may produce mean-shift warnings).
    _, log_plain = fix_numeric_outliers(df)
    capped_plain = {c["column"] for c in log_plain["columns_capped"]}
    assert capped_plain & {"start_lat", "start_lng", "end_lat", "end_lng"}

    preview_before = client.get(f"/api/datasets/{dataset_id}/preview").json()
    outliers_before = next(
        p for p in preview_before["previews"] if p["fix"] == "numeric_outliers"
    )
    assert not (outliers_before.get("protected") or [])
    warn_before = " ".join(outliers_before.get("warnings") or [])

    confirm = {
        "start_lat": "geographic",
        "start_lng": "geographic",
        "end_lat": "geographic",
        "end_lng": "geographic",
        "ride_id": "identifier",
        "started_at": "temporal",
        "ended_at": "temporal",
    }
    put = client.put(f"/api/datasets/{dataset_id}/tags", json={"tags": confirm})
    assert put.status_code == 200

    preview_after = client.get(f"/api/datasets/{dataset_id}/preview").json()
    outliers_after = next(
        p for p in preview_after["previews"] if p["fix"] == "numeric_outliers"
    )
    protected_cols = {p["column"] for p in outliers_after.get("protected") or []}
    assert protected_cols & {"start_lat", "start_lng", "end_lat", "end_lng"}

    warn_after = " ".join(outliers_after.get("warnings") or [])
    for col in ("start_lat", "start_lng", "end_lat", "end_lng"):
        assert f'"{col}" centre moved' not in warn_after
        # Any geo mean-shift warning that existed without tags is gone with tags.
        if f'"{col}" centre moved' in warn_before:
            assert f'"{col}" centre moved' not in warn_after

    _, log_tagged = fix_numeric_outliers(df, tags=confirm)
    capped_tagged = {c["column"] for c in log_tagged["columns_capped"]}
    assert not (capped_tagged & {"start_lat", "start_lng", "end_lat", "end_lng"})


def test_put_unknown_tag_returns_400():
    df = divvy_like(n=30)
    dataset_id = upload(df)
    res = client.put(
        f"/api/datasets/{dataset_id}/tags",
        json={"tags": {"ride_id": "not_a_real_tag"}},
    )
    assert res.status_code == 400


def test_delete_tag_and_tags_survive_reset():
    df = divvy_like(n=30)
    dataset_id = upload(df)
    client.put(
        f"/api/datasets/{dataset_id}/tags",
        json={"tags": {"ride_id": "identifier", "start_lat": "geographic"}},
    )
    client.put(f"/api/datasets/{dataset_id}/target", json={"target_col": None})
    client.post(f"/api/datasets/{dataset_id}/reset")

    tags = client.get(f"/api/datasets/{dataset_id}/tags").json()["confirmed"]
    assert tags["ride_id"] == "identifier"
    assert tags["start_lat"] == "geographic"

    deleted = client.delete(f"/api/datasets/{dataset_id}/tags/ride_id")
    assert deleted.status_code == 200
    assert "ride_id" not in deleted.json()["tags"]
