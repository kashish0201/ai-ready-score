"""
fix_preview.py — show the COST of a fix, not just the gain.

The core idea:
    Every fix trades one property for another. A score that only counts
    issue-absence always rewards the trade and never sees the cost.
    This module measures the cost so the user can decide.

Main entry point:

    previews = preview_fixes(df, target_col, run_quality_checks, compute_ai_ready_score)

Returns one dict per applicable fix:
    {
      'fix': 'missing_values',
      'score_before': 73, 'score_after': 89, 'score_delta': +16,
      'resolves': ['missing_values'],
      'costs': {...},
      'warnings': ['imputation made "Kingsbury St" 22.1x more common than reality'],
      'verdict': 'review'        # 'safe' | 'review' | 'destructive'
    }
"""

import numpy as np
import pandas as pd

import fixes as fx


# ---------------------------------------------------------------------------
# COST METRIC 1: distribution shift (the generic distortion detector)
# ---------------------------------------------------------------------------
def total_variation_distance(before, after):
    """
    How much did a categorical column's distribution move?

    TVD = 0.5 * sum |p_before(c) - p_after(c)|  over all categories c

    0.0 = identical distribution, 1.0 = completely different.
    This is the generic detector: it catches the bike-station problem
    without knowing anything about bike stations.
    """
    p = before.value_counts(normalize=True, dropna=False)
    q = after.value_counts(normalize=True, dropna=False)
    all_cats = p.index.union(q.index)
    p = p.reindex(all_cats, fill_value=0.0)
    q = q.reindex(all_cats, fill_value=0.0)
    return float(0.5 * np.abs(p - q).sum())


def standardised_mean_shift(before, after):
    """
    How much did a numeric column's centre move, in units of its own spread?
    0.0 = unchanged. > 0.2 is a meaningful shift.
    """
    sd = before.std()
    if sd == 0 or pd.isna(sd):
        return 0.0
    return float(abs(after.mean() - before.mean()) / sd)


def top_category_inflation(before, after):
    """
    Did the fix invent a dominant category?
    Returns how many times more common the new top value is vs reality.
    This is the metric that catches mode-imputation damage directly.
    """
    p = before.value_counts(normalize=True, dropna=True)
    q = after.value_counts(normalize=True, dropna=True)
    if len(p) == 0 or len(q) == 0:
        return 1.0, None
    top_value = q.index[0]
    real_share = p.get(top_value, 0.0)
    new_share = q.iloc[0]
    if real_share == 0:
        return float("inf"), top_value
    return float(new_share / real_share), top_value


# ---------------------------------------------------------------------------
# COST MEASUREMENT: compare a dataframe before and after one fix
# ---------------------------------------------------------------------------
ROW_LOSS_WARN = 0.10        # losing >10% of rows is a big deal
TVD_WARN = 0.10             # distribution moved noticeably
INFLATION_WARN = 2.0        # a category became 2x+ more common than reality
MEAN_SHIFT_WARN = 0.20      # numeric centre moved by 0.2 SD


def measure_cost(before_df, after_df):
    """Quantify what changed between the original and the fixed dataframe."""
    costs = {}
    warnings = []

    # --- rows ---
    n_before, n_after = len(before_df), len(after_df)
    if n_after < n_before:
        lost = n_before - n_after
        pct = lost / n_before
        costs["rows_removed"] = int(lost)
        costs["rows_removed_pct"] = round(pct * 100, 1)
        if pct > ROW_LOSS_WARN:
            warnings.append(
                f"deletes {lost:,} rows ({pct:.0%} of the dataset) — "
                f"that much loss usually means the fix doesn't suit this data"
            )
    elif n_after > n_before:
        added = n_after - n_before
        costs["rows_added"] = int(added)
        costs["rows_added_pct"] = round(added / n_before * 100, 1)
        warnings.append(
            f"adds {added:,} synthetic rows ({added/n_before:.0%} of the "
            f"dataset) — these are generated, not observed"
        )

    # --- columns ---
    dropped_cols = [c for c in before_df.columns if c not in after_df.columns]
    if dropped_cols:
        costs["columns_dropped"] = dropped_cols
        warnings.append(
            f"discards {len(dropped_cols)} column(s): {', '.join(dropped_cols)}"
        )

    # --- distribution shifts on surviving columns ---
    shifts = []
    common = [c for c in before_df.columns if c in after_df.columns]

    # only compare like-for-like when row counts match (imputation, capping);
    # if rows were added/removed, distribution change is expected, so we
    # compare shape rather than claim distortion.
    for col in common:
        b, a = before_df[col], after_df[col]

        if pd.api.types.is_numeric_dtype(b) and pd.api.types.is_numeric_dtype(a):
            shift = standardised_mean_shift(b.dropna(), a.dropna())
            if shift > MEAN_SHIFT_WARN:
                shifts.append({"column": col, "type": "numeric",
                               "mean_shift_sd": round(shift, 2)})
                warnings.append(
                    f'"{col}" centre moved {shift:.2f} SD — values were altered'
                )
        else:
            tvd = total_variation_distance(b, a)
            if tvd > TVD_WARN:
                infl, top = top_category_inflation(b, a)
                entry = {"column": col, "type": "categorical",
                         "tvd": round(tvd, 3)}
                if infl > INFLATION_WARN and np.isfinite(infl):
                    entry["top_value"] = str(top)
                    entry["inflation"] = round(infl, 1)
                    warnings.append(
                        f'"{col}": made "{top}" {infl:.1f}x more common than it '
                        f"really is — the tool invented a dominant value"
                    )
                else:
                    warnings.append(
                        f'"{col}" distribution shifted (TVD {tvd:.2f})'
                    )
                shifts.append(entry)

    if shifts:
        costs["distribution_shifts"] = shifts

    return costs, warnings


# ---------------------------------------------------------------------------
# VERDICT: turn costs into a plain-language recommendation
# ---------------------------------------------------------------------------
def verdict_for(costs, warnings):
    """safe | review | destructive"""
    if costs.get("rows_removed_pct", 0) > 25:
        return "destructive"
    for s in costs.get("distribution_shifts", []):
        if s.get("inflation", 0) >= 5:
            return "destructive"
    if warnings:
        return "review"
    return "safe"


# ---------------------------------------------------------------------------
# PREVIEW: run each fix in isolation, report gain AND cost
# ---------------------------------------------------------------------------
SINGLE_FIXES = {
    "mixed_casing": lambda d, t, r, tags=None: fx.fix_mixed_casing(d, tags=tags),
    "duplicate_rows": lambda d, t, r, tags=None: fx.fix_duplicate_rows(d),
    "constant_column": lambda d, t, r, tags=None: fx.fix_constant_columns(
        d, protect=(t,) if t else ()
    ),
    "near_constant_column": lambda d, t, r, tags=None: fx.fix_near_constant_columns(
        d, protect=(t,) if t else ()
    ),
    "high_cardinality": lambda d, t, r, tags=None: fx.fix_high_cardinality(
        d, protect=(t,) if t else ()
    ),
    "missing_values": lambda d, t, r, tags=None: fx.fix_missing_values(
        d, protect=(t,) if t else (), tags=tags
    ),
    "high_correlation": lambda d, t, r, tags=None: fx.fix_high_correlation(
        d, protect=(t,) if t else (), tags=tags
    ),
    "numeric_outliers": lambda d, t, r, tags=None: fx.fix_numeric_outliers(
        d, protect=(t,) if t else (), tags=tags
    ),
    "class_imbalance": lambda d, t, r, tags=None: fx.fix_class_imbalance(
        d, t, target_ratio=r, tags=tags
    ),
}


def preview_fixes(df, target_col, run_quality_checks, compute_ai_ready_score,
                  selected=None, target_ratio=1.5, tags=None):
    """
    For each applicable fix, apply it IN ISOLATION to the original data and
    report: what it resolves, what the score becomes, and what it costs.

    Nothing is applied permanently — this is a preview.
    `tags` are confirmed semantic tags; when present, fixes skip forbidden columns.
    """
    issues_before = run_quality_checks(df, target_col)
    score_before = compute_ai_ready_score(issues_before)
    checks_present = set(issues_before["check"].unique()) if len(issues_before) else set()

    candidates = checks_present & set(SINGLE_FIXES)
    if selected is not None:
        candidates &= set(selected)

    previews = []
    for name in fx.FIX_ORDER:
        if name not in candidates:
            continue

        try:
            fixed, log = SINGLE_FIXES[name](df, target_col, target_ratio, tags)
        except Exception as e:
            previews.append({"fix": name, "error": str(e)})
            continue

        skipped = log.get("skipped") or []
        # Still show a card when the only outcome is tag protection.
        if not log.get("applied") and not skipped:
            continue

        issues_after = run_quality_checks(fixed, target_col)
        score_after = compute_ai_ready_score(issues_after)

        checks_after = set(issues_after["check"].unique()) if len(issues_after) else set()
        resolved = sorted(checks_present - checks_after)
        created = sorted(checks_after - checks_present)

        costs, warnings = measure_cost(df, fixed)

        protected = [
            {"column": item.get("column"), "tag": item.get("tag")}
            for item in skipped
            if item.get("column")
        ]

        previews.append({
            "fix": name,
            "action": log.get("action"),
            "score_before": score_before["score"],
            "score_after": score_after["score"],
            "score_delta": score_after["score"] - score_before["score"],
            "resolves": resolved,
            "creates_new_issues": created,
            "costs": costs,
            "warnings": warnings,
            "verdict": verdict_for(costs, warnings),
            "protected": protected,
            "needs_review": log.get("needs_review") or [],
        })

    return previews


def format_preview(p):
    """Plain-language rendering — this is what the user reads before deciding."""
    if "error" in p:
        return f"[{p['fix']}] failed: {p['error']}"

    icon = {"safe": "OK", "review": "REVIEW", "destructive": "DESTRUCTIVE"}[p["verdict"]]
    lines = [f"[{p['fix']}]  {icon}",
             f"   score {p['score_before']} -> {p['score_after']}  ({p['score_delta']:+d})"]
    if p["resolves"]:
        lines.append(f"   resolves: {', '.join(p['resolves'])}")
    if p["creates_new_issues"]:
        lines.append(f"   CREATES: {', '.join(p['creates_new_issues'])}")
    for w in p["warnings"]:
        lines.append(f"   cost: {w}")
    return "\n".join(lines)