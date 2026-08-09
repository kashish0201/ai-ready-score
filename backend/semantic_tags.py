"""
semantic_tags.py — inference-LIGHT semantic column tagging.

Philosophy: only propose a tag when the evidence is strong and unambiguous.
When in doubt, propose NOTHING and let the column be untagged-but-cautious.
The tool proposes; the human confirms. A wrong silent guess is worse than
an honest "not sure".

Tags and what they forbid/soften (consumed by the fix layer):

    identifier       -> forbid: impute, outlier_cap        (a made-up ID is meaningless)
    geographic       -> forbid: outlier_cap, median_impute (capping moves a place)
    temporal         -> forbid: mode_impute, naive_synth
    categorical_code -> forbid: outlier_cap, median         (median zip = nonsense)
    monetary         -> soften: outlier_cap -> review       (capping money is sometimes ok)
    free_text        -> forbid: one_hot, outlier_cap

Main entry point:

    proposals = propose_tags(df)
    # -> { column: {'tag': str, 'confidence': 'high'|'medium', 'reason': str} }
    # columns with no strong signal are simply absent from the dict.
"""

import re
import numpy as np
import pandas as pd


# name hints are used only as CONFIRMATION alongside value evidence,
# never on their own (except monetary, which is value-ambiguous).
GEO_LAT_HINT = re.compile(r"(\blat\b|latitude\b|breite\b)", re.I)
GEO_LON_HINT = re.compile(r"(\blon\b|\blng\b|\blong\b|\blongitude\b|\blange\b)", re.I)
GEO_ANY_HINT = re.compile(r"(\blat\b|\blatitude\b|\bbreite\b|\blon\b|\blng\b|\blong\b|\blongitude\b|\blange\b|\bcoord\b|\bgeo\b)", re.I)
ID_HINT = re.compile(r"(^id$|_id$|\buuid\b|\bguid\b|\bkey\b|\bcode\b|\bhash\b)", re.I)
MONEY_HINT   = re.compile(r"(price|cost|amount|revenue|salary|pay|fee|charge|usd|eur|gbp|\$)", re.I)


def clean_numeric(series):
    return pd.to_numeric(series, errors="coerce").dropna()


def looks_like_dates(series, sample_size=500):
    """Try parsing a sample as datetimes; return the success fraction."""
    sample = series.dropna().astype(str).head(sample_size)
    if len(sample) == 0:
        return 0.0
    parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    return parsed.notna().mean()


def propose_for_column(name, series):
    """Return (tag, confidence, reason) or None if no strong signal."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return None

    n = len(series)
    uniqueness = series.nunique(dropna=True) / n if n else 0
    is_numeric = pd.api.types.is_numeric_dtype(series)

    # --- TEMPORAL: parses as dates ---------------------------------------
    # Checked BEFORE identifier: timestamps are near-unique, so the identifier
    # rule (>=95% unique) would otherwise swallow them. A column that parses as
    # dates is temporal even if nearly every value is distinct.
    if not is_numeric:
        date_frac = looks_like_dates(series)
        if date_frac >= 0.9:
            return ("temporal", "high",
                    f"{date_frac:.0%} of values parse as dates")

    # --- IDENTIFIER: very high uniqueness + (string or name hint) ---------
    if uniqueness >= 0.95:
        if not is_numeric or ID_HINT.search(name):
            return ("identifier", "high",
                    f"{uniqueness:.0%} unique values" +
                    (" and an id-like name" if ID_HINT.search(name) else ""))

    # --- GEOGRAPHIC: value range + name hint (require BOTH) --------------
    if is_numeric:
        vals = clean_numeric(series)
        if len(vals) > 0:
            in_lat = vals.between(-90, 90).mean()
            in_lon = vals.between(-180, 180).mean()
            has_decimals = (vals != vals.round()).mean() > 0.5

            if GEO_LAT_HINT.search(name) and in_lat >= 0.99:
                return ("geographic", "high",
                        "name suggests latitude and all values fall in [-90, 90]")
            if GEO_LON_HINT.search(name) and in_lon >= 0.99:
                return ("geographic", "high",
                        "name suggests longitude and all values fall in [-180, 180]")
            # weaker: geo-ish name + coordinate-like decimals in range
            if GEO_ANY_HINT.search(name) and in_lat >= 0.99 and has_decimals:
                return ("geographic", "medium",
                        "geo-like name with coordinate-shaped values")

    # --- MONETARY: name hint + non-negative numeric ----------------------
    if is_numeric and MONEY_HINT.search(name):
        vals = clean_numeric(series)
        if len(vals) > 0 and (vals >= 0).mean() >= 0.99:
            return ("monetary", "medium",
                    "money-like name with non-negative values")

    # --- CATEGORICAL CODE: integer, low cardinality, name hint ----------
    if is_numeric:
        vals = clean_numeric(series)
        if len(vals) > 0:
            all_int = (vals == vals.round()).mean() >= 0.99
            low_card = uniqueness < 0.05
            if all_int and low_card and (ID_HINT.search(name) or "zip" in name.lower()
                                         or "code" in name.lower()):
                return ("categorical_code", "medium",
                        "integer codes with low cardinality and a code-like name")

    # --- FREE TEXT: long strings, high uniqueness ------------------------
    if not is_numeric:
        avg_len = non_null.astype(str).str.len().mean()
        if avg_len > 40 and uniqueness > 0.5:
            return ("free_text", "medium",
                    f"long text (avg {avg_len:.0f} chars), mostly unique")

    # no strong signal -> propose nothing (this is the "light" part)
    return None


def propose_tags(df):
    """
    Inspect every column and propose a semantic tag ONLY where evidence is strong.
    Columns with no strong signal are omitted (they stay untagged-but-cautious).
    """
    proposals = {}
    for col in df.columns:
        result = propose_for_column(str(col), df[col])
        if result is not None:
            tag, confidence, reason = result
            proposals[col] = {"tag": tag, "confidence": confidence, "reason": reason}
    return proposals


# # --- what each tag forbids/softens; consumed by the fix layer -------------
# TAG_RULES = {
#     "identifier":       {"forbid": ["missing_values", "numeric_outliers"]},
#     "geographic":       {"forbid": ["numeric_outliers", "missing_values"]},
#     "temporal":         {"forbid": ["missing_values"]},
#     "categorical_code": {"forbid": ["numeric_outliers", "missing_values"]},
#     "monetary":         {"soften": ["numeric_outliers"]},
#     "free_text":        {"forbid": ["numeric_outliers"]},
# }

TAG_RULES = {
    "identifier": {
        "forbid": ["missing_values", "numeric_outliers"],
        "on_violation": "keep_null",          # a missing ID is fine; don't drop rows over it
    },
    "geographic": {
        "forbid": ["numeric_outliers", "missing_values"],
        "on_violation": "drop_row_if_sparse", # drop only if <5% missing, else keep_null
        "sparse_threshold": 0.05,
    },
    "temporal": {
        "forbid": ["missing_values", "numeric_outliers"],
        "on_violation": "keep_null",
    },
    "categorical_code": {
        "forbid": ["numeric_outliers", "missing_values"],
        "on_violation": "keep_null",
    },
    "monetary": {
        "soften": ["numeric_outliers"],        # -> 'review', human decides
        "on_violation": "flag_for_review",
    },
    "free_text": {
        "forbid": ["numeric_outliers"],
        "on_violation": "ignore",
    },
}

def fix_allowed(fix_name, column_tag):
    """
    Returns 'allow' | 'soften' | 'forbid' for a given fix on a column with a tag.
    Untagged columns (tag None) always 'allow' — caution is applied elsewhere.
    """
    if column_tag is None:
        return "allow"
    rules = TAG_RULES.get(column_tag, {})
    if fix_name in rules.get("forbid", []):
        return "forbid"
    if fix_name in rules.get("soften", []):
        return "soften"
    return "allow"

