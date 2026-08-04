"""
fixes.py — the repair toolbox for AI-Ready Score.

One fix per check. Every fix has the SAME shape:

    fixed_df, log = fix_something(df, ...)

  - fixed_df : the repaired dataframe (never modifies the original)
  - log      : dict describing exactly what was done (for the UI + audit trail)

The orchestrator `apply_fixes()` runs them in the RIGHT ORDER and returns a
combined log you can show the user.

ORDER MATTERS (learned the hard way on the churn dataset):
  clean the data FIRST, synthesize LAST — otherwise synthetic rows inherit
  the dirt (missing values, bad casing) from the real rows.
"""

import numpy as np
import pandas as pd

from semantic_tags import fix_allowed


def _column_tag(tags, column):
    if not tags:
        return None
    return tags.get(column)


def _skip_entry(column, tags):
    return {
        "column": column,
        "tag": (tags or {}).get(column),
        "reason": "tag forbids this fix",
    }


def _decide(fix_name, column, tags):
    """Return allow | soften | forbid. tags=None => always allow."""
    if tags is None:
        return "allow"
    return fix_allowed(fix_name, _column_tag(tags, column))


# ---------------------------------------------------------------------------
# 1. DUPLICATE ROWS  ->  drop them
# ---------------------------------------------------------------------------
def fix_duplicate_rows(df):
    """Exact duplicate rows carry no new information and bias training."""
    before = len(df)
    fixed = df.drop_duplicates().reset_index(drop=True)
    removed = before - len(fixed)

    return fixed, {
        "fix": "duplicate_rows",
        "action": "dropped exact duplicate rows",
        "rows_removed": int(removed),
        "rows_before": int(before),
        "rows_after": int(len(fixed)),
        "applied": removed > 0,
    }


# ---------------------------------------------------------------------------
# 2. CONSTANT COLUMNS  ->  drop them
# ---------------------------------------------------------------------------
def fix_constant_columns(df, protect=()):
    """
    A column with one single value teaches a model nothing.
    `protect` = columns never to drop (e.g. the target).
    """
    dropped = []
    for col in df.columns:
        if col in protect:
            continue
        if df[col].nunique(dropna=False) <= 1:
            dropped.append(col)

    fixed = df.drop(columns=dropped) if dropped else df.copy()

    return fixed, {
        "fix": "constant_column",
        "action": "dropped columns with a single value",
        "columns_dropped": dropped,
        "applied": len(dropped) > 0,
    }


# ---------------------------------------------------------------------------
# 3. NEAR-CONSTANT COLUMNS  ->  drop them
# ---------------------------------------------------------------------------
def fix_near_constant_columns(df, threshold=0.95, protect=()):
    """
    e.g. is_active is 'active' in 99.7% of rows -> almost no signal.
    Same threshold as your check_near_constant_columns.
    """
    dropped = []
    for col in df.columns:
        if col in protect:
            continue
        top_share = df[col].value_counts(normalize=True, dropna=False)
        if len(top_share) and top_share.iloc[0] >= threshold:
            dropped.append(col)

    fixed = df.drop(columns=dropped) if dropped else df.copy()

    return fixed, {
        "fix": "near_constant_column",
        "action": f"dropped columns where one value covers >= {threshold:.0%} of rows",
        "columns_dropped": dropped,
        "applied": len(dropped) > 0,
    }


# ---------------------------------------------------------------------------
# 4. HIGH CARDINALITY / ID COLUMNS  ->  drop them
# ---------------------------------------------------------------------------
def fix_high_cardinality(df, threshold=0.5, protect=()):
    """
    A near-unique text column (ride_id, customer_id) is an identifier.
    Useless for learning, and a leakage risk. Drop for modelling.
    Numeric columns are left alone (a price can be near-unique and still useful).
    """
    dropped = []
    for col in df.columns:
        if col in protect:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            continue
        if len(df) == 0:
            continue
        uniqueness = df[col].nunique(dropna=False) / len(df)
        if uniqueness >= threshold:
            dropped.append(col)

    fixed = df.drop(columns=dropped) if dropped else df.copy()

    return fixed, {
        "fix": "high_cardinality",
        "action": f"dropped non-numeric columns that are >= {threshold:.0%} unique (identifiers)",
        "columns_dropped": dropped,
        "applied": len(dropped) > 0,
    }


# ---------------------------------------------------------------------------
# 5. MISSING VALUES  ->  drop hopeless columns, impute the rest
# ---------------------------------------------------------------------------
def fix_missing_values(df, drop_threshold=0.5, protect=(), tags=None):
    """
    Two-tier strategy:
      - column missing MORE than drop_threshold (default 50%) -> drop it,
        imputing that much would be inventing more data than you have.
      - otherwise -> fill:  numeric = median, categorical = most frequent.

    Median (not mean) because it is not dragged around by outliers.
    Semantic tags may forbid or soften acting on a column.
    """
    fixed = df.copy()
    dropped, imputed = [], []
    skipped, needs_review = [], []

    for col in list(fixed.columns):
        n_missing = fixed[col].isna().sum()
        if n_missing == 0:
            continue

        decision = _decide("missing_values", col, tags)
        if decision == "forbid":
            skipped.append(_skip_entry(col, tags))
            continue
        if decision == "soften":
            needs_review.append({
                "column": col,
                "tag": (tags or {}).get(col),
                "reason": "tag softens this fix — skipped pending review",
            })
            continue

        pct = n_missing / len(fixed)

        if pct > drop_threshold and col not in protect:
            fixed = fixed.drop(columns=[col])
            dropped.append({"column": col, "missing_pct": round(pct * 100, 1)})
            continue

        if pd.api.types.is_numeric_dtype(fixed[col]):
            value = fixed[col].median()
            method = "median"
        else:
            mode = fixed[col].mode(dropna=True)
            value = mode.iloc[0] if len(mode) else "unknown"
            method = "most_frequent"

        fixed[col] = fixed[col].fillna(value)
        imputed.append({
            "column": col,
            "method": method,
            "filled": int(n_missing),
            "missing_pct": round(pct * 100, 1),
        })

    return fixed, {
        "fix": "missing_values",
        "action": f"dropped columns >{drop_threshold:.0%} missing; imputed the rest",
        "columns_dropped": dropped,
        "columns_imputed": imputed,
        "skipped": skipped,
        "needs_review": needs_review,
        "applied": bool(dropped or imputed),
    }


# ---------------------------------------------------------------------------
# 6. MIXED CASING  ->  standardise to lowercase
# ---------------------------------------------------------------------------
def fix_mixed_casing(df, tags=None):
    """'Yes' / 'yes' / 'YES' are three categories to a model. Make them one."""
    fixed = df.copy()
    changed = []
    skipped, needs_review = [], []

    for col in fixed.columns:
        if not pd.api.types.is_object_dtype(fixed[col]):
            continue

        decision = _decide("mixed_casing", col, tags)
        if decision == "forbid":
            skipped.append(_skip_entry(col, tags))
            continue
        if decision == "soften":
            needs_review.append({
                "column": col,
                "tag": (tags or {}).get(col),
                "reason": "tag softens this fix — skipped pending review",
            })
            continue

        original_uniques = fixed[col].nunique(dropna=True)
        lowered = fixed[col].astype(str).str.strip().str.lower()
        # only apply if it actually merges categories
        if lowered.nunique(dropna=True) < original_uniques:
            fixed[col] = lowered.where(fixed[col].notna(), np.nan)
            changed.append({
                "column": col,
                "categories_before": int(original_uniques),
                "categories_after": int(lowered.nunique(dropna=True)),
            })

    return fixed, {
        "fix": "mixed_casing",
        "action": "lowercased + trimmed text so equivalent categories merge",
        "columns_changed": changed,
        "skipped": skipped,
        "needs_review": needs_review,
        "applied": len(changed) > 0,
    }


# ---------------------------------------------------------------------------
# 7. NUMERIC OUTLIERS  ->  cap (winsorise), don't delete
# ---------------------------------------------------------------------------
def fix_numeric_outliers(df, protect=(), tags=None):
    """
    IQR rule (same as your check): anything outside
    [Q1 - 1.5*IQR, Q3 + 1.5*IQR] is an outlier.

    We CAP rather than DELETE, because deleting rows throws away every other
    column's data for that row. Capping keeps the row and tames the extreme.

    Geographic / identifier / temporal tags forbid capping.
    Monetary softens (skipped pending review).
    """
    fixed = df.copy()
    capped = []
    skipped, needs_review = [], []

    for col in fixed.columns:
        if col in protect or not pd.api.types.is_numeric_dtype(fixed[col]):
            continue

        q1, q3 = fixed[col].quantile(0.25), fixed[col].quantile(0.75)
        iqr = q3 - q1
        if iqr == 0 or pd.isna(iqr):
            continue

        low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        n_out = int(((fixed[col] < low) | (fixed[col] > high)).sum())
        if n_out == 0:
            continue

        # Tag gate only when we would otherwise act on this column.
        decision = _decide("numeric_outliers", col, tags)
        if decision == "forbid":
            skipped.append(_skip_entry(col, tags))
            continue
        if decision == "soften":
            needs_review.append({
                "column": col,
                "tag": (tags or {}).get(col),
                "reason": "tag softens this fix — skipped pending review",
            })
            continue

        fixed[col] = fixed[col].clip(lower=low, upper=high)
        capped.append({
            "column": col,
            "values_capped": n_out,
            "lower_bound": round(float(low), 3),
            "upper_bound": round(float(high), 3),
        })

    return fixed, {
        "fix": "numeric_outliers",
        "action": "capped extreme values to the IQR fence (kept the rows)",
        "columns_capped": capped,
        "skipped": skipped,
        "needs_review": needs_review,
        "applied": len(capped) > 0,
    }


# ---------------------------------------------------------------------------
# 8. HIGH CORRELATION  ->  drop one of each redundant pair
# ---------------------------------------------------------------------------
def fix_high_correlation(df, threshold=0.9, protect=(), tags=None):
    """
    If two features are ~the same information (corr >= 0.9), keep one.
    Drops the SECOND of each pair. Never drops the target.
    `tags` accepted for a uniform signature; correlation drop is not tag-gated.
    """
    numeric = df.select_dtypes(include=[np.number])
    numeric = numeric.drop(columns=[c for c in protect if c in numeric.columns],
                           errors="ignore")

    dropped, pairs = [], []
    if numeric.shape[1] >= 2:
        corr = numeric.corr().abs()
        upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))

        for col in upper.columns:
            for row in upper.index:
                value = upper.loc[row, col]
                if pd.notna(value) and value >= threshold:
                    if col not in dropped and row not in dropped:
                        dropped.append(col)
                        pairs.append({"kept": row, "dropped": col,
                                      "correlation": round(float(value), 3)})

    fixed = df.drop(columns=dropped) if dropped else df.copy()

    return fixed, {
        "fix": "high_correlation",
        "action": f"dropped one column from each pair correlated >= {threshold}",
        "pairs": pairs,
        "columns_dropped": dropped,
        "skipped": [],
        "needs_review": [],
        "applied": len(dropped) > 0,
    }


# ---------------------------------------------------------------------------
# 9. CLASS IMBALANCE  ->  synthetic minority rows (SDV)
#    (the one you already built — folded in here, LAST in the order)
# ---------------------------------------------------------------------------
def fix_class_imbalance(df, target_col, target_ratio=1.5, tags=None):
    """Generate synthetic minority-class rows until ratio <= target_ratio.

    Identifier / temporal columns are dropped from the frame handed to the
    synthesizer so we never invent IDs or timestamps. Rejoined as NaN on new rows.
    """
    if target_col is None or target_col not in df.columns:
        return df.copy(), {"fix": "class_imbalance", "applied": False,
                           "reason": "no valid target column",
                           "skipped": [], "needs_review": []}

    counts = df[target_col].value_counts(dropna=False)
    if len(counts) < 2:
        return df.copy(), {"fix": "class_imbalance", "applied": False,
                           "reason": "target has fewer than 2 classes",
                           "skipped": [], "needs_review": []}

    majority_count, minority_count = int(counts.iloc[0]), int(counts.iloc[-1])
    minority_class = counts.index[-1]
    current_ratio = majority_count / minority_count

    if current_ratio <= target_ratio:
        return df.copy(), {"fix": "class_imbalance", "applied": False,
                           "reason": "already balanced",
                           "ratio_before": round(current_ratio, 2),
                           "skipped": [], "needs_review": []}

    minority_df = df[df[target_col] == minority_class]
    if len(minority_df) < 2:
        return df.copy(), {"fix": "class_imbalance", "applied": False,
                           "reason": "not enough minority rows to learn from",
                           "skipped": [], "needs_review": []}

    desired = int(np.ceil(majority_count / target_ratio))
    n_generate = desired - minority_count

    # Prefer dropping identifier/temporal columns from the synthesizer input
    # rather than inventing values for them.
    drop_for_synth = []
    skipped = []
    if tags:
        for col, tag in tags.items():
            if col == target_col or col not in minority_df.columns:
                continue
            if tag in ("identifier", "temporal"):
                drop_for_synth.append(col)
                skipped.append({
                    "column": col,
                    "tag": tag,
                    "reason": "excluded from synthesizer (do not invent this column)",
                })

    synth_source = minority_df.drop(columns=drop_for_synth, errors="ignore")

    # import here so the module still loads if sdv isn't installed
    from sdv.metadata import Metadata
    from sdv.single_table import GaussianCopulaSynthesizer

    metadata = Metadata.detect_from_dataframe(synth_source)
    synth = GaussianCopulaSynthesizer(metadata)
    synth.fit(synth_source)
    new_rows = synth.sample(num_rows=n_generate)
    new_rows[target_col] = minority_class
    for col in drop_for_synth:
        if col not in new_rows.columns:
            new_rows[col] = np.nan

    # Align columns with original before concat
    new_rows = new_rows.reindex(columns=df.columns)

    fixed = pd.concat([df, new_rows], ignore_index=True)
    fixed = fixed.sample(frac=1, random_state=42).reset_index(drop=True)

    new_counts = fixed[target_col].value_counts(dropna=False)

    return fixed, {
        "fix": "class_imbalance",
        "action": f"generated {n_generate} synthetic '{minority_class}' rows",
        "synthetic_rows_added": int(n_generate),
        "ratio_before": round(current_ratio, 2),
        "ratio_after": round(float(new_counts.iloc[0] / new_counts.iloc[-1]), 2),
        "skipped": skipped,
        "needs_review": [],
        "synth_columns_excluded": drop_for_synth,
        "applied": True,
    }


# ---------------------------------------------------------------------------
# ORCHESTRATOR — run the fixes in the correct order
# ---------------------------------------------------------------------------
FIX_ORDER = [
    "mixed_casing",          # normalise text first, so dedupe catches more
    "constant_column",       # drop dead columns before imputing them
    "near_constant_column",
    "high_cardinality",      # drop IDs before dedupe — dropping IDs can create new exact duplicates
    "duplicate_rows",        # then remove redundant rows (including those newly exposed)
    "missing_values",        # impute what's left
    "high_correlation",      # drop redundant features
    "numeric_outliers",      # tame extremes
    "class_imbalance",       # synthesise LAST, on clean data
]


def apply_fixes(df, target_col=None, selected=None, target_ratio=1.5, tags=None):
    """
    Apply fixes in the correct order.

    selected : list of fix names to run. None = run all of them.
    tags     : optional confirmed semantic tags (column -> tag).
    Returns (fixed_df, logs) where logs is a list of per-fix dicts.
    """
    protect = (target_col,) if target_col else ()
    selected = set(selected) if selected is not None else set(FIX_ORDER)

    fixed = df.copy()
    logs = []

    for name in FIX_ORDER:
        if name not in selected:
            continue

        if name == "mixed_casing":
            fixed, log = fix_mixed_casing(fixed, tags=tags)
        elif name == "duplicate_rows":
            fixed, log = fix_duplicate_rows(fixed)
        elif name == "constant_column":
            fixed, log = fix_constant_columns(fixed, protect=protect)
        elif name == "near_constant_column":
            fixed, log = fix_near_constant_columns(fixed, protect=protect)
        elif name == "high_cardinality":
            fixed, log = fix_high_cardinality(fixed, protect=protect)
        elif name == "missing_values":
            fixed, log = fix_missing_values(fixed, protect=protect, tags=tags)
        elif name == "high_correlation":
            fixed, log = fix_high_correlation(fixed, protect=protect, tags=tags)
        elif name == "numeric_outliers":
            fixed, log = fix_numeric_outliers(fixed, protect=protect, tags=tags)
        elif name == "class_imbalance":
            fixed, log = fix_class_imbalance(
                fixed, target_col, target_ratio, tags=tags
            )
        else:
            continue

        logs.append(log)

    return fixed, logs