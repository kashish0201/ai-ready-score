"""JSON serialisation helpers for numpy / pandas values."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def to_jsonable(obj):
    """
    Recursively convert numpy scalars via .item(), NaN/inf to None,
    and numpy arrays / pandas Index to lists.
    """
    if obj is None:
        return None

    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]

    if isinstance(obj, (np.integer,)):
        return int(obj)

    if isinstance(obj, (np.floating,)):
        number = float(obj)
        if math.isnan(number) or math.isinf(number):
            return None
        return number

    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj

    if isinstance(obj, (np.bool_,)):
        return bool(obj)

    if isinstance(obj, np.ndarray):
        return to_jsonable(obj.tolist())

    if isinstance(obj, pd.Index):
        return to_jsonable(obj.tolist())

    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()

    if isinstance(obj, pd.Series):
        return to_jsonable(obj.tolist())

    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass

    if hasattr(obj, "item") and not isinstance(obj, (bytes, str, bytearray)):
        try:
            return to_jsonable(obj.item())
        except Exception:
            return str(obj)

    return obj


def issues_to_records(issues_df: pd.DataFrame) -> list:
    if issues_df is None or len(issues_df) == 0:
        return []
    records = issues_df.replace({np.nan: None}).to_dict(orient="records")
    return to_jsonable(records)
