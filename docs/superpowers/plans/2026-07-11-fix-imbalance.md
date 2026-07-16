# Fix Class Imbalance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a “Fix class imbalance” section under the AI-Ready score that calls `rebalance_with_synthetic`, re-scores the rebalanced copy, shows before/after metrics, and offers a CSV download — without replacing the uploaded dataset.

**Architecture:** Persist analysis results in `st.session_state` so Fix survives Streamlit reruns. When `class_imbalance` is present, show a dedicated Fix section under the score. On click, call `synthetic_rebalance.rebalance_with_synthetic`, re-run existing quality checks + scoring on the rebalanced frame, store Fix outputs in session, and render before/after + download. Original `df` stays unchanged.

**Tech Stack:** Streamlit, pandas, numpy, matplotlib, SDV (`synthetic_rebalance.py`)

**Spec:** `docs/superpowers/specs/2026-07-11-fix-imbalance-design.md`

**Note:** This workspace may not be a git repository. Skip commit steps if `git status` fails; otherwise commit after each task.

---

## File structure

| File | Responsibility |
|------|----------------|
| `app.py` | UI helpers for Fix visibility/state; session_state analysis persistence; Fix section UI + wiring |
| `synthetic_rebalance.py` | Unchanged — import `rebalance_with_synthetic` only |
| `style.css` | Optional: only if Fix section needs a small style hook for consistency |

No new modules required. Keep helpers in `app.py` next to existing UI helpers to match the current single-file app pattern.

---

### Task 1: Session helpers for analysis + Fix state

**Files:**
- Modify: `app.py` (UI Helper Functions section, after `convert_df_to_csv`)

- [ ] **Step 1: Add import and helper functions**

Near the top of `app.py` (with other imports), add:

```python
from synthetic_rebalance import rebalance_with_synthetic
```

After `convert_df_to_csv`, add:

```python
FIX_STATE_KEYS = (
    "rebalance_report",
    "fixed_score_result",
    "fixed_issues_df",
    "rebalanced_csv",
)

ANALYSIS_STATE_KEYS = (
    "analysis_df",
    "analysis_target_col",
    "issues_df",
    "score_result",
)


def clear_fix_state():
    for key in FIX_STATE_KEYS:
        if key in st.session_state:
            del st.session_state[key]


def clear_analysis_state():
    clear_fix_state()
    for key in ANALYSIS_STATE_KEYS:
        if key in st.session_state:
            del st.session_state[key]


def has_class_imbalance(issues_df):
    if issues_df is None or len(issues_df) == 0:
        return False
    if "check" not in issues_df.columns:
        return False
    return bool((issues_df["check"] == "class_imbalance").any())


def store_analysis_results(df, target_col, issues_df, score_result):
    clear_fix_state()
    st.session_state["analysis_df"] = df
    st.session_state["analysis_target_col"] = target_col
    st.session_state["issues_df"] = issues_df
    st.session_state["score_result"] = score_result
```

Use `analysis_df` (not `df`) as the session key so it does not collide with the local `df` variable name in mental models; the uploaded frame for Fix must be the same object that was analyzed.

- [ ] **Step 2: Smoke-check helpers in a Python REPL (optional but quick)**

Run from project root:

```bash
python -c "
import pandas as pd
# minimal stand-in without importing streamlit session
issues = pd.DataFrame([{'check': 'class_imbalance'}])
assert (issues['check'] == 'class_imbalance').any()
issues2 = pd.DataFrame([{'check': 'missing_values'}])
assert not (issues2['check'] == 'class_imbalance').any()
print('ok')
"
```

Expected: `ok`

- [ ] **Step 3: Commit (if git repo exists)**

```bash
git add app.py
git commit -m "$(cat <<'EOF'
Add session helpers for analysis and fix imbalance state.

EOF
)"
```

---

### Task 2: Persist analysis results and render from session_state

**Files:**
- Modify: `app.py` (Streamlit App section, from file upload through analysis display)

**Why:** Today results only render inside `if run_button:`. Clicking Fix would rerun the script and wipe the score UI. Analysis must be stored and re-rendered whenever session has results for the current upload.

- [ ] **Step 1: Track upload identity and clear stale state**

Replace the start of the `if uploaded_file is not None:` block so loading a new file clears prior analysis/Fix state. Use the uploader’s file identity:

```python
if uploaded_file is not None:
    try:
        file_id = f"{uploaded_file.name}:{uploaded_file.size}"
        if st.session_state.get("uploaded_file_id") != file_id:
            st.session_state["uploaded_file_id"] = file_id
            clear_analysis_state()

        df = pd.read_csv(uploaded_file)
        # ... existing preview / overview / target selectbox unchanged ...
```

- [ ] **Step 2: On Run, store results instead of only rendering inside the button branch**

Change the run button block to:

```python
        run_button = st.button("Run AI-Readiness Analysis")

        if run_button:
            with st.spinner("Analyzing dataset..."):
                issues_df = run_quality_checks(df, target_col=target_col)
                score_result = compute_ai_ready_score(issues_df)
            store_analysis_results(df, target_col, issues_df, score_result)
```

- [ ] **Step 3: Render score + issues from session_state when present**

Immediately after the run-button block, add a render path that uses session state (so it survives Fix clicks):

```python
        if "score_result" in st.session_state and "issues_df" in st.session_state:
            score_result = st.session_state["score_result"]
            issues_df = st.session_state["issues_df"]

            st.markdown(
                f"""
                <div class="score-card">
                    <div class="score-number">{score_result['score']}/100</div>
                    <div class="score-label">AI-Ready Score — {score_result['grade']}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            score_col1, score_col2, score_col3, score_col4 = st.columns(4)
            score_col1.metric("Score", f"{score_result['score']}/100")
            score_col2.metric("Grade", score_result["grade"])
            score_col3.metric("Total Issues", score_result["total_issues"])
            score_col4.metric("High Severity", score_result["high_issues"])

            st.info(score_result["summary"])

            # --- Fix section goes here in Task 3 ---

            st.header("Issue Summary")
            # ... move the existing Issue Summary / charts / recommendations /
            #     download-issues block here, still using issues_df / score_result ...
```

Move the existing Issue Summary UI (from `st.header("Issue Summary")` through the issues download button) out of `if run_button:` into this `if "score_result" in st.session_state` block, **below** where the Fix section will be inserted in Task 3.

Do **not** put Fix below Issue Summary — spec requires Fix **under the score card**, before Issue Summary.

- [ ] **Step 4: Manual check**

```bash
streamlit run app.py
```

Upload a CSV, run analysis, confirm score appears. Change nothing else and confirm the score still shows after interacting with widgets (e.g. changing nothing / page still has results after a rerun triggered by selectbox if you re-select the same target — if changing target should not auto-clear until re-run, that is fine; only new file or new Run clears Fix state via `store_analysis_results` / file_id).

Expected: Score and issues remain visible after a Streamlit rerun without clicking Run again.

- [ ] **Step 5: Commit (if git repo exists)**

```bash
git add app.py
git commit -m "$(cat <<'EOF'
Persist AI-readiness analysis results in session state.

EOF
)"
```

---

### Task 3: Fix class imbalance section (UI + rebalance wiring)

**Files:**
- Modify: `app.py` (insert Fix section under score summary, before Issue Summary)

- [ ] **Step 1: Insert Fix section under score `st.info`**

Place this block where the Task 2 comment `# --- Fix section goes here in Task 3 ---` is:

```python
            analysis_target = st.session_state.get("analysis_target_col")
            if (
                analysis_target is not None
                and has_class_imbalance(issues_df)
            ):
                st.header("Fix class imbalance")
                st.write(
                    "Generate synthetic minority-class rows (SDV Gaussian Copula) "
                    "to improve class balance. Uses a default majority:minority "
                    "target ratio of 1.5. The original uploaded data is not replaced."
                )

                if st.button("Fix", key="fix_imbalance_button"):
                    with st.spinner("Rebalancing dataset with synthetic samples..."):
                        try:
                            source_df = st.session_state["analysis_df"]
                            rebalanced_df, report = rebalance_with_synthetic(
                                source_df,
                                analysis_target,
                            )
                            st.session_state["rebalance_report"] = report

                            if report.get("status") == "success":
                                fixed_issues = run_quality_checks(
                                    rebalanced_df,
                                    target_col=analysis_target,
                                )
                                fixed_score = compute_ai_ready_score(fixed_issues)
                                st.session_state["fixed_issues_df"] = fixed_issues
                                st.session_state["fixed_score_result"] = fixed_score
                                st.session_state["rebalanced_csv"] = convert_df_to_csv(
                                    rebalanced_df
                                )
                            else:
                                for key in (
                                    "fixed_score_result",
                                    "fixed_issues_df",
                                    "rebalanced_csv",
                                ):
                                    if key in st.session_state:
                                        del st.session_state[key]
                        except Exception as fix_error:
                            clear_fix_state()
                            st.error(
                                f"Fix failed while rebalancing: {fix_error}"
                            )

                report = st.session_state.get("rebalance_report")
                if report is not None:
                    status = report.get("status")
                    if status == "success":
                        fixed_score = st.session_state["fixed_score_result"]
                        fixed_issues = st.session_state["fixed_issues_df"]

                        st.success(
                            f"Added {report['synthetic_rows_added']} synthetic "
                            f"rows for minority class '{report['minority_class']}'."
                        )

                        before_after = st.columns(4)
                        before_after[0].metric(
                            "Score",
                            f"{fixed_score['score']}/100",
                            delta=fixed_score["score"] - score_result["score"],
                        )
                        before_after[1].metric(
                            "Rows",
                            report["rows_after"],
                            delta=report["rows_after"] - report["rows_before"],
                        )
                        before_after[2].metric(
                            "Imbalance ratio",
                            report["ratio_after"],
                            delta=round(
                                report["ratio_after"] - report["ratio_before"],
                                2,
                            ),
                            delta_color="inverse",
                        )
                        before_after[3].metric(
                            "Synthetic rows",
                            report["synthetic_rows_added"],
                        )

                        st.caption(
                            f"Before: score {score_result['score']}/100, "
                            f"{report['rows_before']} rows, "
                            f"ratio {report['ratio_before']}. "
                            f"After: score {fixed_score['score']}/100, "
                            f"{report['rows_after']} rows, "
                            f"ratio {report['ratio_after']}."
                        )

                        fix_sev1, fix_sev2, fix_sev3 = st.columns(3)
                        fix_sev1.metric("High (after)", fixed_score["high_issues"])
                        fix_sev2.metric("Medium (after)", fixed_score["medium_issues"])
                        fix_sev3.metric("Low (after)", fixed_score["low_issues"])

                        st.subheader("Issues after Fix")
                        if len(fixed_issues) == 0:
                            st.success("No major issues found after rebalancing.")
                        else:
                            st.dataframe(fixed_issues)

                        st.download_button(
                            label="Download rebalanced CSV",
                            data=st.session_state["rebalanced_csv"],
                            file_name="rebalanced_dataset.csv",
                            mime="text/csv",
                            key="download_rebalanced_csv",
                        )
                    elif status in ("skipped", "failed"):
                        st.warning(
                            f"Fix did not rebalance the data: {report.get('reason', status)}"
                        )
```

- [ ] **Step 2: Verify `sdv` is importable in the app environment**

```bash
python -c "from synthetic_rebalance import rebalance_with_synthetic; print('import ok')"
```

Expected: `import ok`  
If import fails, install SDV in the same environment used for Streamlit:

```bash
pip install sdv
```

- [ ] **Step 3: Manual end-to-end test (imbalanced data)**

Create a tiny imbalanced CSV for testing if you do not already have one:

```bash
python -c "
import pandas as pd
df = pd.DataFrame({
    'x': list(range(20)),
    'y': [0]*18 + [1]*2,
})
df.to_csv('/tmp/imbalanced_demo.csv', index=False)
print('wrote /tmp/imbalanced_demo.csv')
"
```

Then:

```bash
streamlit run app.py
```

1. Upload `/tmp/imbalanced_demo.csv`
2. Select target `y`
3. Run analysis → confirm `class_imbalance` appears and score is shown
4. Confirm **Fix class imbalance** section appears under the score
5. Click **Fix** → confirm before/after metrics, issues-after table, and download
6. Confirm Dataset Preview still shows 20 rows (original not replaced)
7. Download CSV and confirm row count matches `rows_after` from the report

- [ ] **Step 4: Manual negative tests**

1. Upload a balanced CSV (e.g. 10/10 classes) with target selected → run analysis → Fix section must **not** appear  
2. Run with target `None` → Fix section must **not** appear even if other issues exist  
3. (Optional) Dataset with minority class count `< 2` → Fix shows warning with reason, no download

- [ ] **Step 5: Commit (if git repo exists)**

```bash
git add app.py
git commit -m "$(cat <<'EOF'
Add Fix class imbalance section using synthetic rebalance.

EOF
)"
```

---

### Task 4: Final verification against the spec

**Files:** none (checklist only)

- [ ] **Step 1: Spec coverage checklist**

Confirm each item from `docs/superpowers/specs/2026-07-11-fix-imbalance-design.md`:

- [ ] Fix only when analysis ran + `class_imbalance` + target set  
- [ ] Section under score card (before Issue Summary)  
- [ ] Uses `rebalance_with_synthetic` unchanged  
- [ ] Re-runs quality checks + score on rebalanced copy  
- [ ] Before/after metrics + download  
- [ ] Original upload not replaced  
- [ ] skip/fail → warning with reason  
- [ ] unexpected error → `st.error`, original analysis still visible  
- [ ] New upload / re-run analysis clears Fix state  

- [ ] **Step 2: Done**

No further code unless a checklist item fails — then fix the gap in `app.py` and re-run the relevant manual test.

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|------------------|------|
| Session state for analysis + Fix | Task 1–2 |
| Fix section under score | Task 3 |
| Visibility rules | Task 3 condition |
| rebalance → re-score → download | Task 3 |
| Keep original df | Task 3 (`analysis_df` never overwritten by rebalance) |
| skip/fail/error handling | Task 3 |
| Clear Fix on new file / re-run | Task 1 helpers + Task 2 file_id / `store_analysis_results` |
| No changes to `synthetic_rebalance.py` | All tasks |
| Manual test plan | Task 3–4 |

No TBD placeholders. Helper names are consistent: `clear_fix_state`, `clear_analysis_state`, `has_class_imbalance`, `store_analysis_results`, `FIX_STATE_KEYS`, `ANALYSIS_STATE_KEYS`.
