# Fix Class Imbalance — Design Spec

**Date:** 2026-07-11  
**Status:** Approved for planning  
**Scope:** Integrate `synthetic_rebalance.py` into the Streamlit AI-Ready Score app via a dedicated Fix section.

## Goal

After a user runs AI-readiness analysis and class imbalance is detected, they can click **Fix** to generate synthetic minority-class rows, see before/after readiness impact, and download the rebalanced CSV — without replacing the original uploaded dataset in the session.

## Decisions (from brainstorming)

| Decision | Choice |
|----------|--------|
| Post-Fix behavior | Rebalance + re-run analysis + before/after scores + CSV download |
| When Fix appears | Only after analysis, and only if `class_imbalance` is in issues (target selected) |
| Working dataset | Keep original upload as source of truth; Fix is one-shot preview + download |
| UI placement | Dedicated “Fix class imbalance” section directly under the score card |
| `target_ratio` | Default `1.5` from `rebalance_with_synthetic`; not exposed in UI for v1 |
| Other issue types | Out of scope — no Fix buttons for missing values, duplicates, etc. |

## Architecture

```
Upload CSV → select target → Run Analysis
        ↓
  score + issues (session_state)
        ↓
  if class_imbalance present:
        ↓
  [Fix class imbalance section]
        ↓
  rebalance_with_synthetic(df, target_col)  # does not mutate original df
        ↓
  run_quality_checks + compute_ai_ready_score on rebalanced_df
        ↓
  show before/after + report + download CSV
```

- **Entry point:** `app.py` (Streamlit UI)
- **Rebalance engine:** `synthetic_rebalance.rebalance_with_synthetic` — used as-is; no logic changes required in `synthetic_rebalance.py`
- **Quality/scoring:** existing `run_quality_checks` and `compute_ai_ready_score`

## Session state

Persist across Streamlit reruns:

| Key | When set | Purpose |
|-----|----------|---------|
| `df` | After successful CSV load / analysis path | Original uploaded data (never replaced by Fix) |
| `target_col` | After analysis | Target used for imbalance + rebalance |
| `issues_df` | After analysis | Original issues |
| `score_result` | After analysis | Original score dict |
| `rebalance_report` | After Fix attempt | Status/reason/metrics from rebalance |
| `fixed_score_result` | After successful Fix | Score on rebalanced data |
| `fixed_issues_df` | After successful Fix | Issues on rebalanced data |
| `rebalanced_csv` | After successful Fix | Encoded CSV bytes for download |

Clear Fix-related keys (`rebalance_report`, `fixed_*`, `rebalanced_csv`) when a new file is uploaded or analysis is re-run.

**Note:** Analysis results must live in `session_state` so the Fix button click (which triggers a rerun) still has access to `df`, `target_col`, and the original score.

## UI

### Visibility

Show the Fix section only when:

1. Analysis has been run (results in session), and  
2. `issues_df` contains at least one row with `check == "class_imbalance"`, and  
3. `target_col` is not `None`

### Layout (under score card / summary)

1. **Header:** “Fix class imbalance”
2. **Copy:** Short explanation that Fix adds synthetic minority-class rows (SDV / Gaussian Copula) to improve class balance; uses default majority:minority target ratio of 1.5
3. **Button:** “Fix”
4. **On success:**
   - Metrics: score before → after; rows before → after; ratio before → after; synthetic rows added
   - Status/summary from `rebalance_report`
   - Updated issue counts (high/medium/low) plus the full fixed issues table
   - Download button: `rebalanced_dataset.csv`
5. **On skip/fail** (`status` in `skipped` / `failed`): `st.warning` with `report["reason"]` — no download, no fake success
6. **On unexpected exception:** `st.error`; original analysis UI remains visible

## Data flow (Fix click)

1. Read `df` and `target_col` from session state  
2. Call `rebalanced_df, report = rebalance_with_synthetic(df, target_col)`  
3. If `report["status"] != "success"`: store report, show warning, stop  
4. Else: `fixed_issues = run_quality_checks(rebalanced_df, target_col)`  
5. `fixed_score = compute_ai_ready_score(fixed_issues)`  
6. Store report, fixed score/issues, and `rebalanced_df.to_csv(...)` bytes  
7. Render before/after UI + download

## Error handling

| Case | Behavior |
|------|----------|
| No imbalance / no target | Section hidden |
| Rebalance skipped/failed | Warning with `reason` |
| SDV or other runtime error | Error message; original results unchanged |
| Empty/invalid CSV | Existing upload error path (unchanged) |

## Non-goals

- Fixing non-imbalance issues  
- Configurable `target_ratio` in the UI  
- Replacing session `df` with rebalanced data  
- Changing scoring penalties or quality-check thresholds  
- Automated unit tests in this iteration (manual verification)

## Manual test plan

1. Upload an imbalanced CSV with a clear target column  
2. Run analysis → confirm score and `class_imbalance` issue  
3. Confirm Fix section appears under the score  
4. Click Fix → confirm before/after metrics and download works  
5. Confirm original preview/overview still reflect the uploaded file  
6. Upload a balanced (or no-imbalance) dataset → Fix section does not appear  
7. If possible: minority class with &lt; 2 rows → Fix shows failed reason gracefully  

## Files to change

| File | Change |
|------|--------|
| `app.py` | Import rebalance; session_state for analysis + Fix; Fix section UI; wire rebalance → re-score → download |
| `synthetic_rebalance.py` | No changes expected |
| `style.css` | Optional minor styles for Fix section if needed for consistency |

## Dependencies

- Existing: `streamlit`, `pandas`, `numpy`, `matplotlib`  
- Required for Fix: `sdv` (already used by `synthetic_rebalance.py`) — ensure it is installed in the app environment
