"""FastAPI app for AI-Ready Score — dataset store + one-fix-at-a-time previews."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
# fix_preview.py does `import fixes as fx` — backend/ must be on sys.path.
for path in (str(BACKEND_DIR), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from backend.jsonutil import issues_to_records, to_jsonable
from backend.quality import (
    compute_ai_ready_score,
    get_dataset_overview,
    run_quality_checks,
)
from backend import store
from semantic_tags import TAG_RULES, propose_tags
import fix_preview  # noqa: E402  — uses sibling `fixes` on BACKEND_DIR path

app = FastAPI(title="AI-Ready Score API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

KNOWN_TAGS = set(TAG_RULES.keys())


class TargetBody(BaseModel):
    target_col: str | None = None


class ApplyBody(BaseModel):
    fix: str
    target_ratio: float = 1.5


class TagsBody(BaseModel):
    tags: dict[str, str]


def _read_csv_bytes(raw: bytes) -> pd.DataFrame:
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Could not parse CSV: {exc}"
        ) from exc
    if len(df) == 0:
        raise HTTPException(status_code=400, detail="CSV has no data rows")
    return df


def _require_entry(dataset_id: str) -> dict:
    try:
        return store.get_entry(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown dataset_id") from exc


def _entry_tags(entry: dict) -> dict[str, str]:
    return dict(entry.get("tags") or {})


def _score_payload(entry: dict) -> dict:
    current = entry["current_df"]
    target = entry["target_col"]
    issues_df = run_quality_checks(current, target_col=target)
    score = compute_ai_ready_score(issues_df)

    if entry.get("original_score") is None:
        original_issues = run_quality_checks(
            entry["original_df"], target_col=target
        )
        entry["original_score"] = compute_ai_ready_score(original_issues)

    return {
        "score": score["score"],
        "grade": score["grade"],
        "summary": score["summary"],
        "high_issues": score["high_issues"],
        "medium_issues": score["medium_issues"],
        "low_issues": score["low_issues"],
        "total_issues": score["total_issues"],
        "issues": issues_to_records(issues_df),
        "round_num": entry["round_num"],
        "original_score": entry["original_score"],
        "history": entry["history"],
        "target_col": target,
        "tags": _entry_tags(entry),
        "overview": get_dataset_overview(current),
        "columns": list(current.columns),
        "preview_rows": _preview_rows(current),
    }


def _preview_rows(df: pd.DataFrame, n: int = 10) -> list:
    head = df.head(n)
    records = head.replace({pd.NA: None}).astype(object).where(
        pd.notnull(head), None
    ).to_dict(orient="records")
    return to_jsonable(records)


def _run_previews(entry: dict, target_ratio: float = 1.5, selected=None) -> list:
    tags = _entry_tags(entry) or None
    return fix_preview.preview_fixes(
        entry["current_df"],
        entry["target_col"],
        run_quality_checks,
        compute_ai_ready_score,
        selected=selected,
        target_ratio=target_ratio,
        tags=tags,
    )


def _get_or_build_previews(dataset_id: str, entry: dict, target_ratio: float) -> list:
    tags = _entry_tags(entry)
    tags_key = store.tags_cache_key(tags)
    cached = store.get_preview_cache(
        dataset_id, entry["round_num"], target_ratio, tags_key
    )
    if cached is not None:
        return cached
    previews = _run_previews(entry, target_ratio=target_ratio, selected=None)
    store.set_preview_cache(
        dataset_id, entry["round_num"], target_ratio, previews, tags_key
    )
    return previews


@app.post("/api/datasets")
async def create_dataset(file: UploadFile = File(...)):
    raw = await file.read()
    df = await run_in_threadpool(_read_csv_bytes, raw)
    filename = file.filename or "upload.csv"

    def _create():
        created = store.create_dataset(df, filename)
        overview = get_dataset_overview(df)
        return {
            "dataset_id": created["dataset_id"],
            "filename": created["filename"],
            "overview": overview,
            "columns": created["columns"],
            "target_candidates": created["target_candidates"],
            "preview_rows": _preview_rows(df),
        }

    return to_jsonable(await run_in_threadpool(_create))


@app.put("/api/datasets/{dataset_id}/target")
async def set_target(dataset_id: str, body: TargetBody):
    entry = _require_entry(dataset_id)
    target = body.target_col
    if target is not None and target not in entry["original_df"].columns:
        raise HTTPException(status_code=400, detail=f"Unknown target_col: {target}")

    def _set():
        store.set_target(dataset_id, target)
        return _score_payload(store.get_entry(dataset_id))

    return to_jsonable(await run_in_threadpool(_set))


@app.get("/api/datasets/{dataset_id}/score")
async def get_score(dataset_id: str):
    _require_entry(dataset_id)

    def _score():
        return _score_payload(store.get_entry(dataset_id))

    return to_jsonable(await run_in_threadpool(_score))


@app.get("/api/datasets/{dataset_id}/tags")
async def get_tags(dataset_id: str):
    entry = _require_entry(dataset_id)

    def _tags():
        current = store.get_entry(dataset_id)
        proposed = propose_tags(current["current_df"])
        return {
            "proposed": proposed,
            "confirmed": _entry_tags(current),
        }

    return to_jsonable(await run_in_threadpool(_tags))


@app.put("/api/datasets/{dataset_id}/tags")
async def put_tags(dataset_id: str, body: TagsBody):
    _require_entry(dataset_id)
    unknown = sorted({tag for tag in body.tags.values() if tag not in KNOWN_TAGS})
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown tag(s): {', '.join(unknown)}",
        )

    def _put():
        stored = store.set_tags(dataset_id, body.tags)
        return {"tags": stored}

    return to_jsonable(await run_in_threadpool(_put))


@app.delete("/api/datasets/{dataset_id}/tags/{column}")
async def delete_tag(dataset_id: str, column: str):
    _require_entry(dataset_id)

    def _delete():
        stored = store.clear_column_tag(dataset_id, column)
        return {"tags": stored}

    return to_jsonable(await run_in_threadpool(_delete))


@app.get("/api/datasets/{dataset_id}/preview")
async def get_preview(
    dataset_id: str,
    target_ratio: float = 1.5,
    selected: str | None = None,
):
    """
    Full preview is cached per (dataset_id, round_num, target_ratio, tags).
    Pass selected=fix_name to refresh a single card (e.g. class_imbalance ratio).
    """
    _require_entry(dataset_id)
    selected_list = [selected] if selected else None

    def _preview():
        current = store.get_entry(dataset_id)
        if selected_list is None:
            previews = _get_or_build_previews(dataset_id, current, target_ratio)
        else:
            previews = _run_previews(
                current, target_ratio=target_ratio, selected=selected_list
            )
        return {
            "round_num": current["round_num"],
            "previews": previews,
            "tags": _entry_tags(current),
        }

    return to_jsonable(await run_in_threadpool(_preview))


@app.post("/api/datasets/{dataset_id}/apply")
async def apply_fix(dataset_id: str, body: ApplyBody):
    _require_entry(dataset_id)
    fix_name = body.fix
    if fix_name not in fix_preview.SINGLE_FIXES:
        raise HTTPException(status_code=400, detail=f"Unknown fix name: {fix_name}")

    def _apply():
        current = store.get_entry(dataset_id)
        df = current["current_df"]
        target = current["target_col"]
        tags = _entry_tags(current) or None
        ratio = float(body.target_ratio)

        issues_before = run_quality_checks(df, target_col=target)
        score_before = compute_ai_ready_score(issues_before)
        present = set(issues_before["check"].unique()) if len(issues_before) else set()
        if fix_name not in present:
            raise HTTPException(
                status_code=400,
                detail=f"Fix '{fix_name}' is not currently applicable",
            )

        try:
            fixed_df, log = fix_preview.SINGLE_FIXES[fix_name](
                df, target, ratio, tags
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        if not log.get("applied"):
            raise HTTPException(
                status_code=400,
                detail=f"Fix '{fix_name}' did not apply: {log.get('reason', 'no change')}",
            )

        issues_after = run_quality_checks(fixed_df, target_col=target)
        score_after = compute_ai_ready_score(issues_after)

        store.apply_one_fix(
            dataset_id,
            fix_name,
            fixed_df,
            log,
            score_before["score"],
            score_after["score"],
        )
        updated = store.get_entry(dataset_id)
        score_body = _score_payload(updated)
        previews = _get_or_build_previews(dataset_id, updated, ratio)
        return {
            **score_body,
            "applied_fix": fix_name,
            "applied_log": log,
            "previews": previews,
        }

    try:
        result = await run_in_threadpool(_apply)
    except HTTPException:
        raise
    return to_jsonable(result)


@app.post("/api/datasets/{dataset_id}/reset")
async def reset_dataset(dataset_id: str):
    _require_entry(dataset_id)

    def _reset():
        store.reset_dataset(dataset_id)
        return _score_payload(store.get_entry(dataset_id))

    return to_jsonable(await run_in_threadpool(_reset))


@app.get("/api/datasets/{dataset_id}/download")
async def download_dataset(dataset_id: str):
    entry = _require_entry(dataset_id)

    def _csv() -> bytes:
        return store.get_entry(dataset_id)["current_df"].to_csv(index=False).encode(
            "utf-8"
        )

    data = await run_in_threadpool(_csv)
    filename = entry.get("filename") or "dataset.csv"
    stem = filename.rsplit(".", 1)[0]
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{stem}_fixed.csv"'
        },
    )
