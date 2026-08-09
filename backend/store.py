"""
In-memory dataset store.

Note: this store is per-process and will not survive a restart or work across
multiple workers. Entries older than 1 hour are evicted on access to bound memory.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pandas as pd

# Per-process only — not shared across workers / restarts.
_DATASETS: dict[str, dict] = {}
_PREVIEW_CACHE: dict[tuple, list] = {}

TTL = timedelta(hours=1)
TARGET_UNIQUE_LIMIT = 20


def current_time() -> datetime:
    return datetime.now(timezone.utc)


def evict_stale() -> None:
    cutoff = current_time() - TTL
    stale = [did for did, entry in _DATASETS.items() if entry["created_at"] < cutoff]
    for did in stale:
        _DATASETS.pop(did, None)
        invalidate_preview_cache(did)


def invalidate_preview_cache(dataset_id: str) -> None:
    keys = [key for key in _PREVIEW_CACHE if key[0] == dataset_id]
    for key in keys:
        _PREVIEW_CACHE.pop(key, None)


def target_candidates(df: pd.DataFrame, max_uniques: int = TARGET_UNIQUE_LIMIT) -> list[str]:
    return [
        col
        for col in df.columns
        if df[col].nunique(dropna=False) <= max_uniques
    ]


def create_dataset(df: pd.DataFrame, filename: str) -> dict:
    evict_stale()
    dataset_id = str(uuid4())
    original = df.copy()
    entry = {
        "original_df": original,
        "current_df": original.copy(),
        "target_col": None,
        # Confirmed semantic tags: column -> tag string. Empty until the user saves.
        # Survives target changes and reset (tags describe columns, not fixes).
        "tags": {},
        "history": [],
        "round_num": 1,
        "filename": filename,
        "created_at": current_time(),
        "original_score": None,
    }
    _DATASETS[dataset_id] = entry
    return {
        "dataset_id": dataset_id,
        "filename": filename,
        "columns": list(df.columns),
        "target_candidates": target_candidates(df),
        "entry": entry,
    }


def get_entry(dataset_id: str) -> dict:
    evict_stale()
    entry = _DATASETS.get(dataset_id)
    if entry is None:
        raise KeyError(dataset_id)
    return entry


def set_target(dataset_id: str, target_col: str | None) -> dict:
    entry = get_entry(dataset_id)
    entry["target_col"] = target_col
    entry["current_df"] = entry["original_df"].copy()
    entry["history"] = []
    entry["round_num"] = 1
    entry["original_score"] = None
    invalidate_preview_cache(dataset_id)
    return entry


def reset_dataset(dataset_id: str) -> dict:
    entry = get_entry(dataset_id)
    entry["current_df"] = entry["original_df"].copy()
    entry["history"] = []
    entry["round_num"] = 1
    # tags intentionally preserved
    invalidate_preview_cache(dataset_id)
    return entry


def get_tags(dataset_id: str) -> dict[str, str]:
    entry = get_entry(dataset_id)
    return dict(entry.get("tags") or {})


def set_tags(dataset_id: str, tags: dict[str, str]) -> dict[str, str]:
    entry = get_entry(dataset_id)
    entry["tags"] = {str(k): str(v) for k, v in tags.items()}
    invalidate_preview_cache(dataset_id)
    return dict(entry["tags"])


def clear_column_tag(dataset_id: str, column: str) -> dict[str, str]:
    entry = get_entry(dataset_id)
    tags = dict(entry.get("tags") or {})
    tags.pop(column, None)
    entry["tags"] = tags
    invalidate_preview_cache(dataset_id)
    return dict(tags)


def tags_cache_key(tags: dict | None) -> str:
    """Stable fingerprint so preview cache invalidates when tags change."""
    if not tags:
        return ""
    return "|".join(f"{k}={tags[k]}" for k in sorted(tags))


def apply_one_fix(
    dataset_id: str,
    fix_name: str,
    fixed_df: pd.DataFrame,
    log: dict,
    score_before: int,
    score_after: int,
) -> dict:
    entry = get_entry(dataset_id)
    entry["current_df"] = fixed_df
    entry["history"].append({
        "round": entry["round_num"],
        "fix": fix_name,
        "score_before": score_before,
        "score_after": score_after,
        "log": deepcopy(log) if isinstance(log, dict) else log,
    })
    entry["round_num"] = int(entry["round_num"]) + 1
    invalidate_preview_cache(dataset_id)
    return entry


def get_preview_cache(
    dataset_id: str,
    round_num: int,
    target_ratio: float,
    tags_key: str = "",
) -> list | None:
    return _PREVIEW_CACHE.get((dataset_id, round_num, float(target_ratio), tags_key))


def set_preview_cache(
    dataset_id: str,
    round_num: int,
    target_ratio: float,
    previews: list,
    tags_key: str = "",
) -> None:
    _PREVIEW_CACHE[(dataset_id, round_num, float(target_ratio), tags_key)] = previews
