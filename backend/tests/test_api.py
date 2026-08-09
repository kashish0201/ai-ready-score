from io import BytesIO

import pandas as pd
import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

from backend.main import MAX_UPLOAD_BYTES, app, validate_upload_size

client = TestClient(app)


def test_upload_size_over_200_mb_is_rejected():
    upload_file = UploadFile(
        filename="large.csv",
        file=BytesIO(b""),
        size=MAX_UPLOAD_BYTES + 1,
    )

    with pytest.raises(HTTPException) as exc:
        validate_upload_size(upload_file)

    assert exc.value.status_code == 413
    assert exc.value.detail == "CSV file exceeds the 200 MB upload limit"


def test_upload_size_exactly_200_mb_is_accepted():
    upload_file = UploadFile(
        filename="limit.csv",
        file=BytesIO(b""),
        size=MAX_UPLOAD_BYTES,
    )

    validate_upload_size(upload_file)


def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def upload(df: pd.DataFrame, name: str = "data.csv") -> str:
    files = {"file": (name, csv_bytes(df), "text/csv")}
    res = client.post("/api/datasets", files=files)
    assert res.status_code == 200, res.text
    return res.json()["dataset_id"]


def test_upload_returns_target_candidates():
    df = pd.DataFrame({
        "id": [f"r{i}" for i in range(25)],
        "label": [0] * 20 + [1] * 5,
    })
    files = {"file": ("data.csv", csv_bytes(df), "text/csv")}
    res = client.post("/api/datasets", files=files)
    assert res.status_code == 200
    body = res.json()
    assert "dataset_id" in body
    assert "label" in body["target_candidates"]
    assert "id" not in body["target_candidates"]


def test_score_and_preview_after_target():
    df = pd.DataFrame({"x": list(range(20)), "y": [0] * 18 + [1] * 2})
    dataset_id = upload(df)

    res = client.put(
        f"/api/datasets/{dataset_id}/target",
        json={"target_col": "y"},
    )
    assert res.status_code == 200
    score = res.json()
    assert "score" in score
    assert score["round_num"] == 1
    assert score["original_score"]["score"] == score["score"]

    preview = client.get(f"/api/datasets/{dataset_id}/preview")
    assert preview.status_code == 200
    body = preview.json()
    assert "previews" in body
    assert any(p["fix"] == "class_imbalance" for p in body["previews"])


def test_apply_one_fix_updates_history_and_round():
    df = pd.DataFrame({"x": [1, 1, 2], "y": [0, 0, 1]})
    dataset_id = upload(df)
    client.put(f"/api/datasets/{dataset_id}/target", json={"target_col": None})

    res = client.post(
        f"/api/datasets/{dataset_id}/apply",
        json={"fix": "duplicate_rows"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["round_num"] == 2
    assert len(body["history"]) == 1
    assert body["history"][0]["fix"] == "duplicate_rows"
    assert "previews" in body


def test_apply_unknown_fix_returns_400():
    df = pd.DataFrame({"x": [1, 2], "y": [0, 1]})
    dataset_id = upload(df)
    client.put(f"/api/datasets/{dataset_id}/target", json={"target_col": "y"})
    res = client.post(
        f"/api/datasets/{dataset_id}/apply",
        json={"fix": "not_a_real_fix"},
    )
    assert res.status_code == 400


def test_apply_inapplicable_fix_returns_400():
    df = pd.DataFrame({"x": [1, 2, 3], "y": [0, 1, 0]})
    dataset_id = upload(df)
    client.put(f"/api/datasets/{dataset_id}/target", json={"target_col": "y"})
    res = client.post(
        f"/api/datasets/{dataset_id}/apply",
        json={"fix": "duplicate_rows"},
    )
    assert res.status_code == 400


def test_unknown_dataset_returns_404():
    res = client.get("/api/datasets/does-not-exist/score")
    assert res.status_code == 404


def test_reset_restores_original():
    df = pd.DataFrame({"x": [1, 1, 2], "y": [0, 0, 1]})
    dataset_id = upload(df)
    client.put(f"/api/datasets/{dataset_id}/target", json={"target_col": None})
    client.post(
        f"/api/datasets/{dataset_id}/apply",
        json={"fix": "duplicate_rows"},
    )
    res = client.post(f"/api/datasets/{dataset_id}/reset")
    assert res.status_code == 200
    body = res.json()
    assert body["round_num"] == 1
    assert body["history"] == []
    assert body["overview"]["rows"] == 3


def test_download_returns_csv():
    df = pd.DataFrame({"x": [1, 2], "y": [0, 1]})
    dataset_id = upload(df)
    res = client.get(f"/api/datasets/{dataset_id}/download")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "x,y" in res.text


def test_preview_json_handles_inf_via_to_jsonable():
    from backend.jsonutil import to_jsonable

    assert to_jsonable(float("inf")) is None
    assert to_jsonable(float("nan")) is None


def test_empty_csv_returns_400():
    files = {"file": ("bad.csv", b"", "text/csv")}
    res = client.post("/api/datasets", files=files)
    assert res.status_code == 400
