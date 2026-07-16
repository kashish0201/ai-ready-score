# Vite + FastAPI Terminal Report UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Terminal Report web app (Vite React + FastAPI) that analyzes CSV readiness and can Fix class imbalance via `synthetic_rebalance.py`, without changing Streamlit `app.py`.

**Architecture:** Extract quality/scoring into `backend/quality.py`. FastAPI exposes `POST /api/analyze` and `POST /api/fix`. Vite React SPA (dark terminal UI, two-column layout) calls those APIs with multipart uploads and keeps the File in memory for Fix.

**Tech Stack:** FastAPI, uvicorn, pandas, numpy, sdv, python-multipart, Vite, React, CSS variables

**Spec:** `docs/superpowers/specs/2026-07-11-vite-fastapi-terminal-ui-design.md`

**Note:** Skip git commit steps if this folder is not a git repository.

---

## File structure

| Path | Responsibility |
|------|----------------|
| `backend/quality.py` | Streamlit-free quality checks + scoring + overview |
| `backend/main.py` | FastAPI app, CORS, `/api/analyze`, `/api/fix` |
| `backend/requirements.txt` | Python deps |
| `backend/tests/test_quality.py` | Unit tests for checks/score helpers |
| `backend/tests/test_api.py` | API tests via TestClient |
| `frontend/` | Vite React Terminal Report UI |
| `synthetic_rebalance.py` | Unchanged |
| `app.py` | Unchanged |

Run uvicorn from **repo root**:

```bash
uvicorn backend.main:app --reload --port 8000
```

so `from synthetic_rebalance import rebalance_with_synthetic` works when `backend/main.py` adds the repo root to `sys.path`.

---

### Task 1: Extract `backend/quality.py` with tests

**Files:**
- Create: `backend/__init__.py` (empty)
- Create: `backend/quality.py`
- Create: `backend/tests/__init__.py` (empty)
- Create: `backend/tests/test_quality.py`
- Create: `backend/requirements.txt`

- [ ] **Step 1: Write failing tests for overview + imbalance + score**

Create `backend/tests/test_quality.py`:

```python
import pandas as pd
import pytest

from backend.quality import (
    compute_ai_ready_score,
    get_dataset_overview,
    run_quality_checks,
)


def test_get_dataset_overview_counts():
    df = pd.DataFrame({"a": [1, 2], "b": ["x", None]})
    overview = get_dataset_overview(df)
    assert overview["rows"] == 2
    assert overview["columns"] == 2
    assert overview["missing_pct"] == pytest.approx(25.0)
    assert overview["numeric_columns"] == 1
    assert overview["categorical_columns"] == 1


def test_class_imbalance_detected():
    df = pd.DataFrame({"x": range(20), "y": [0] * 18 + [1] * 2})
    issues = run_quality_checks(df, target_col="y")
    assert (issues["check"] == "class_imbalance").any()


def test_no_imbalance_when_balanced():
    df = pd.DataFrame({"x": range(10), "y": [0] * 5 + [1] * 5})
    issues = run_quality_checks(df, target_col="y")
    if len(issues) == 0:
        assert True
    else:
        assert not (issues["check"] == "class_imbalance").any()


def test_compute_ai_ready_score_empty():
    result = compute_ai_ready_score(pd.DataFrame(columns=[
        "check", "column", "severity", "metric", "value",
        "explanation", "recommendation",
    ]))
    assert result["score"] == 100
    assert result["grade"] == "Excellent"
```

- [ ] **Step 2: Run tests — expect import failure**

```bash
cd /Users/kashishphulwani/Documents/machine_learning/AI_ready
python3 -m pytest backend/tests/test_quality.py -v
```

Expected: FAIL (`ModuleNotFoundError` or import error for `backend.quality`)

- [ ] **Step 3: Create `backend/requirements.txt`**

```text
fastapi
uvicorn
pandas
numpy
python-multipart
sdv
pytest
httpx
```

- [ ] **Step 4: Implement `backend/quality.py`**

Copy the following from `app.py` into `backend/quality.py` (no Streamlit imports): all `check_*` functions, `run_quality_checks`, `compute_ai_ready_score`, and `get_dataset_overview`. Keep signatures identical. Add only:

```python
import pandas as pd
import numpy as np
```

Ensure `run_quality_checks` returns a DataFrame with the same columns as in `app.py`. Ensure `compute_ai_ready_score` returns the same dict keys. Ensure `get_dataset_overview` returns the same dict keys as in `app.py`.

Also create empty `backend/__init__.py` and `backend/tests/__init__.py`.

- [ ] **Step 5: Re-run tests — expect PASS**

```bash
python3 -m pytest backend/tests/test_quality.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit (if git exists)**

```bash
git add backend/
git commit -m "$(cat <<'EOF'
Extract quality checks into backend.quality module.

EOF
)"
```

---

### Task 2: FastAPI `/api/analyze` and `/api/fix`

**Files:**
- Create: `backend/main.py`
- Create: `backend/tests/test_api.py`

- [ ] **Step 1: Write failing API tests**

Create `backend/tests/test_api.py`:

```python
import io

import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def _csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def test_analyze_imbalanced_returns_score_and_flag():
    df = pd.DataFrame({"x": list(range(20)), "y": [0] * 18 + [1] * 2})
    files = {"file": ("data.csv", _csv_bytes(df), "text/csv")}
    data = {"target_col": "y"}
    res = client.post("/api/analyze", files=files, data=data)
    assert res.status_code == 200
    body = res.json()
    assert "score" in body
    assert body["has_class_imbalance"] is True
    assert body["overview"]["rows"] == 20
    assert len(body["preview_rows"]) > 0


def test_analyze_bad_csv_returns_400():
    files = {"file": ("bad.csv", b"not,a,valid\n\"unclosed", "text/csv")}
    res = client.post("/api/analyze", files=files, data={})
    assert res.status_code == 400


def test_fix_requires_target():
    df = pd.DataFrame({"x": [1, 2], "y": [0, 1]})
    files = {"file": ("data.csv", _csv_bytes(df), "text/csv")}
    res = client.post("/api/fix", files=files, data={})
    assert res.status_code == 400


def test_fix_success_returns_csv_string():
    df = pd.DataFrame({"x": list(range(20)), "y": [0] * 18 + [1] * 2})
    files = {"file": ("data.csv", _csv_bytes(df), "text/csv")}
    data = {"target_col": "y"}
    res = client.post("/api/fix", files=files, data=data)
    assert res.status_code == 200
    body = res.json()
    assert body["report"]["status"] == "success"
    assert isinstance(body["rebalanced_csv"], str)
    assert "score_after" in body
```

- [ ] **Step 2: Run API tests — expect fail**

```bash
python3 -m pytest backend/tests/test_api.py -v
```

Expected: FAIL (cannot import `backend.main`)

- [ ] **Step 3: Implement `backend/main.py`**

```python
import io
import sys
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from synthetic_rebalance import rebalance_with_synthetic
from backend.quality import (
    compute_ai_ready_score,
    get_dataset_overview,
    run_quality_checks,
)

app = FastAPI(title="AI-Ready Score API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _read_csv(file: UploadFile) -> pd.DataFrame:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        return pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {exc}") from exc


def _issues_records(issues_df: pd.DataFrame) -> list:
    if issues_df is None or len(issues_df) == 0:
        return []
    records = issues_df.to_dict(orient="records")
    for row in records:
        if hasattr(row.get("value"), "item"):
            row["value"] = row["value"].item()
        elif row.get("value") is not None:
            try:
                row["value"] = float(row["value"]) if not isinstance(row["value"], str) else row["value"]
            except (TypeError, ValueError):
                row["value"] = str(row["value"])
    return records


def _has_class_imbalance(issues_df: pd.DataFrame) -> bool:
    if issues_df is None or len(issues_df) == 0:
        return False
    return bool((issues_df["check"] == "class_imbalance").any())


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    target_col: str | None = Form(None),
):
    df = await _read_csv(file)
    target = target_col if target_col not in (None, "", "None") else None
    issues_df = run_quality_checks(df, target_col=target)
    score = compute_ai_ready_score(issues_df)
    overview = get_dataset_overview(df)
    preview = df.head(10).where(pd.notnull(df.head(10)), None).to_dict(orient="records")
    return {
        "columns": list(df.columns),
        "overview": overview,
        "preview_rows": preview,
        "target_col": target,
        "score": score,
        "issues": _issues_records(issues_df),
        "has_class_imbalance": _has_class_imbalance(issues_df) and target is not None,
    }


@app.post("/api/fix")
async def fix_imbalance(
    file: UploadFile = File(...),
    target_col: str | None = Form(None),
):
    if not target_col or target_col in ("", "None"):
        raise HTTPException(status_code=400, detail="target_col is required")
    df = await _read_csv(file)
    issues_before = run_quality_checks(df, target_col=target_col)
    score_before = compute_ai_ready_score(issues_before)
    try:
        rebalanced_df, report = rebalance_with_synthetic(df, target_col)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if report.get("status") != "success":
        return {
            "report": report,
            "score_before": score_before,
            "score_after": None,
            "issues_after": [],
            "rebalanced_csv": None,
        }

    issues_after = run_quality_checks(rebalanced_df, target_col=target_col)
    score_after = compute_ai_ready_score(issues_after)
    return {
        "report": report,
        "score_before": score_before,
        "score_after": score_after,
        "issues_after": _issues_records(issues_after),
        "rebalanced_csv": rebalanced_df.to_csv(index=False),
    }
```

- [ ] **Step 4: Re-run API tests**

```bash
python3 -m pytest backend/tests/test_api.py -v
```

Expected: PASS (Fix test may take ~10–30s due to SDV)

If `test_analyze_bad_csv_returns_400` fails because pandas is lenient, change the payload to `b""` (empty) which must return 400.

- [ ] **Step 5: Commit (if git exists)**

```bash
git add backend/main.py backend/tests/test_api.py
git commit -m "$(cat <<'EOF'
Add FastAPI analyze and fix endpoints.

EOF
)"
```

---

### Task 3: Scaffold Vite React frontend

**Files:**
- Create: `frontend/` via Vite

- [ ] **Step 1: Scaffold**

```bash
cd /Users/kashishphulwani/Documents/machine_learning/AI_ready
npm create vite@latest frontend -- --template react
cd frontend && npm install
```

- [ ] **Step 2: Configure proxy in `frontend/vite.config.js`**

Replace contents with:

```js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
```

- [ ] **Step 3: Verify dev server starts**

```bash
cd frontend && npm run dev
```

Expected: Vite ready on `http://localhost:5173/`

Stop the server after confirming.

- [ ] **Step 4: Commit (if git exists)**

```bash
git add frontend
git commit -m "$(cat <<'EOF'
Scaffold Vite React frontend with API proxy.

EOF
)"
```

---

### Task 4: API client + Terminal Report styles + shell layout

**Files:**
- Create: `frontend/src/api.js`
- Create: `frontend/src/styles.css` (replace default)
- Modify: `frontend/src/main.jsx`
- Modify: `frontend/src/App.jsx`
- Create: `frontend/src/components/Hero.jsx`
- Create: `frontend/src/components/ErrorBanner.jsx`
- Create: `frontend/src/components/UploadPanel.jsx`
- Delete or ignore: `frontend/src/App.css`, `frontend/src/index.css` defaults as needed

- [ ] **Step 1: Create `frontend/src/api.js`**

```js
export async function analyzeCsv(file, targetCol) {
  const form = new FormData();
  form.append("file", file);
  if (targetCol) form.append("target_col", targetCol);
  const res = await fetch("/api/analyze", { method: "POST", body: form });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || "Analyze failed");
  return body;
}

export async function fixImbalance(file, targetCol) {
  const form = new FormData();
  form.append("file", file);
  form.append("target_col", targetCol);
  const res = await fetch("/api/fix", { method: "POST", body: form });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || "Fix failed");
  return body;
}

export async function peekCsvHeaders(file) {
  const text = await file.slice(0, 65536).text();
  const firstLine = text.split(/\r?\n/).find((line) => line.trim().length > 0);
  if (!firstLine) return [];
  return firstLine.split(",").map((h) => h.trim().replace(/^"|"$/g, ""));
}
```

- [ ] **Step 2: Write `frontend/src/styles.css` with Terminal Report tokens**

Include at minimum:

```css
:root {
  --bg: #0b1220;
  --panel: #111827;
  --border: #1f2937;
  --text: #e5e7eb;
  --muted: #9ca3af;
  --green: #34d399;
  --green-dim: #065f46;
  --amber: #fbbf24;
  --red: #f87171;
  --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  --sans: system-ui, -apple-system, Segoe UI, sans-serif;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font-family: var(--sans);
}

#root { min-height: 100vh; }

.app-shell {
  max-width: 1120px;
  margin: 0 auto;
  padding: 1.5rem 1.25rem 3rem;
}

.prompt {
  font-family: var(--mono);
  color: var(--green);
  font-size: 0.85rem;
  margin-bottom: 0.35rem;
}

.brand {
  font-size: 2rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0;
}

.subtitle {
  color: var(--muted);
  margin: 0.35rem 0 1.5rem;
}

.layout {
  display: grid;
  grid-template-columns: 1.35fr 0.9fr;
  gap: 1rem;
  align-items: start;
}

@media (max-width: 860px) {
  .layout { grid-template-columns: 1fr; }
}

.panel {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem 1.1rem;
  margin-bottom: 0.85rem;
}

.panel-label {
  font-family: var(--mono);
  font-size: 0.75rem;
  color: var(--muted);
  margin-bottom: 0.65rem;
}

.dropzone {
  border: 1px dashed #374151;
  border-radius: 6px;
  padding: 1.25rem;
  text-align: center;
  color: var(--muted);
  cursor: pointer;
}

.dropzone:hover, .dropzone.active {
  border-color: var(--green);
  color: var(--green);
}

.row {
  display: flex;
  gap: 0.65rem;
  align-items: center;
  margin-top: 0.75rem;
  flex-wrap: wrap;
}

select, button {
  font: inherit;
}

select {
  flex: 1;
  min-width: 140px;
  background: var(--bg);
  color: var(--text);
  border: 1px solid #374151;
  border-radius: 6px;
  padding: 0.55rem 0.65rem;
}

button {
  background: var(--green-dim);
  color: #a7f3d0;
  border: 1px solid #047857;
  border-radius: 6px;
  padding: 0.55rem 0.9rem;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.12s ease, background 0.12s ease;
}

button:hover:not(:disabled) {
  background: #047857;
}

button:active:not(:disabled) {
  transform: translateY(1px);
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.score-panel {
  border-color: var(--green-dim);
  background: #052e2b;
  text-align: center;
  animation: slideUp 0.35s ease;
}

.score-number {
  font-size: 3.5rem;
  font-weight: 700;
  color: var(--green);
  line-height: 1;
}

.fade-in {
  animation: fadeIn 0.4s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.error-banner {
  background: #3f1d1d;
  border: 1px solid var(--red);
  color: #fecaca;
  border-radius: 8px;
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
  font-family: var(--mono);
  font-size: 0.85rem;
}

.issue {
  border-left: 3px solid var(--amber);
  background: #1f2937;
  border-radius: 0 6px 6px 0;
  padding: 0.65rem 0.75rem;
  margin-bottom: 0.5rem;
  font-size: 0.9rem;
}

.issue.high { border-left-color: var(--red); }
.issue.medium { border-left-color: var(--amber); }
.issue.low { border-left-color: var(--green); }

.metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 0.5rem;
}

.metric {
  background: var(--bg);
  border-radius: 6px;
  padding: 0.55rem 0.65rem;
}

.metric span {
  display: block;
  font-family: var(--mono);
  font-size: 0.7rem;
  color: var(--muted);
}

.preview-table {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--mono);
  font-size: 0.75rem;
}

.preview-table th,
.preview-table td {
  border-bottom: 1px solid var(--border);
  padding: 0.35rem 0.4rem;
  text-align: left;
}

.sev-bars {
  display: flex;
  gap: 0.35rem;
  align-items: flex-end;
  height: 48px;
  margin-top: 0.5rem;
}

.sev-bar {
  flex: 1;
  background: #1f2937;
  border-radius: 4px 4px 0 0;
  min-height: 4px;
}
```

- [ ] **Step 3: Create small presentational components**

`frontend/src/components/Hero.jsx`:

```jsx
export default function Hero() {
  return (
    <header>
      <div className="prompt">$ ai-ready check --csv data.csv</div>
      <h1 className="brand">AI-Ready Score</h1>
      <p className="subtitle">Zero-config data readiness for ML</p>
    </header>
  );
}
```

`frontend/src/components/ErrorBanner.jsx`:

```jsx
export default function ErrorBanner({ message }) {
  if (!message) return null;
  return <div className="error-banner">{message}</div>;
}
```

`frontend/src/components/UploadPanel.jsx`:

```jsx
export default function UploadPanel({
  fileName,
  columns,
  targetCol,
  onTargetChange,
  onFile,
  onRun,
  loading,
}) {
  return (
    <section className="panel">
      <div className="panel-label">upload</div>
      <label className="dropzone">
        <input
          type="file"
          accept=".csv,text/csv"
          hidden
          onChange={(e) => onFile(e.target.files?.[0] || null)}
        />
        {fileName ? fileName : "drop CSV or browse"}
      </label>
      <div className="row">
        <select
          value={targetCol || ""}
          onChange={(e) => onTargetChange(e.target.value || null)}
          disabled={!columns.length}
        >
          <option value="">target: none</option>
          {columns.map((c) => (
            <option key={c} value={c}>
              target: {c}
            </option>
          ))}
        </select>
        <button type="button" onClick={onRun} disabled={!fileName || loading}>
          {loading ? "Analyzing…" : "Run analysis"}
        </button>
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Wire a minimal `App.jsx` shell** (upload + headers only; results in Task 5)

```jsx
import { useState } from "react";
import "./styles.css";
import Hero from "./components/Hero";
import ErrorBanner from "./components/ErrorBanner";
import UploadPanel from "./components/UploadPanel";
import { peekCsvHeaders } from "./api";

export default function App() {
  const [file, setFile] = useState(null);
  const [columns, setColumns] = useState([]);
  const [targetCol, setTargetCol] = useState(null);
  const [error, setError] = useState(null);

  async function handleFile(next) {
    setError(null);
    setFile(next);
    setTargetCol(null);
    if (!next) {
      setColumns([]);
      return;
    }
    try {
      setColumns(await peekCsvHeaders(next));
    } catch (err) {
      setError(err.message);
      setColumns([]);
    }
  }

  return (
    <div className="app-shell">
      <Hero />
      <ErrorBanner message={error} />
      <UploadPanel
        fileName={file?.name}
        columns={columns}
        targetCol={targetCol}
        onTargetChange={setTargetCol}
        onFile={handleFile}
        onRun={() => {}}
        loading={false}
      />
    </div>
  );
}
```

Update `frontend/src/main.jsx` to import only `./styles.css` (remove `index.css` if present):

```jsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

- [ ] **Step 5: Visual check**

```bash
cd frontend && npm run dev
```

Expected: dark terminal hero + upload panel. Stop when done.

- [ ] **Step 6: Commit (if git exists)**

```bash
git add frontend/src
git commit -m "$(cat <<'EOF'
Add terminal theme shell and upload panel.

EOF
)"
```

---

### Task 5: Results UI — score, issues, overview, preview, Fix

**Files:**
- Create: `frontend/src/components/OverviewStrip.jsx`
- Create: `frontend/src/components/PreviewTable.jsx`
- Create: `frontend/src/components/ScorePanel.jsx`
- Create: `frontend/src/components/IssuesList.jsx`
- Create: `frontend/src/components/FixPanel.jsx`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Add remaining components**

`OverviewStrip.jsx` — render `overview` metrics in `.metrics` / `.metric`.

`PreviewTable.jsx` — table from `preview_rows` + `columns`.

`ScorePanel.jsx` — large score, grade, summary, high/medium/low counts, simple `.sev-bars` heights proportional to counts.

`IssuesList.jsx` — map issues to `.issue.{severity}` cards with check, column, explanation.

`FixPanel.jsx`:

```jsx
export default function FixPanel({
  visible,
  loading,
  onFix,
  result,
}) {
  if (!visible) return null;

  function downloadCsv() {
    if (!result?.rebalanced_csv) return;
    const blob = new Blob([result.rebalanced_csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "rebalanced_dataset.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="panel fade-in">
      <div className="panel-label">fix // class_imbalance</div>
      <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>
        Generate synthetic minority-class rows (SDV). Original upload is not replaced.
      </p>
      <button type="button" onClick={onFix} disabled={loading}>
        {loading ? "Rebalancing…" : "Fix"}
      </button>
      {result?.report?.status === "success" && (
        <div style={{ marginTop: "0.85rem" }}>
          <div className="metrics">
            <div className="metric">
              <span>score</span>
              {result.score_before?.score} → {result.score_after?.score}
            </div>
            <div className="metric">
              <span>rows</span>
              {result.report.rows_before} → {result.report.rows_after}
            </div>
            <div className="metric">
              <span>ratio</span>
              {result.report.ratio_before} → {result.report.ratio_after}
            </div>
            <div className="metric">
              <span>synthetic</span>
              {result.report.synthetic_rows_added}
            </div>
          </div>
          <button type="button" style={{ marginTop: "0.75rem" }} onClick={downloadCsv}>
            Download rebalanced CSV
          </button>
        </div>
      )}
      {(result?.report?.status === "skipped" || result?.report?.status === "failed") && (
        <p style={{ color: "var(--amber)", fontFamily: "var(--mono)", fontSize: "0.85rem" }}>
          {result.report.reason || result.report.status}
        </p>
      )}
    </section>
  );
}
```

Implement the other components with the same CSS classes; keep them presentational.

- [ ] **Step 2: Wire full `App.jsx`**

State: `file`, `columns`, `targetCol`, `error`, `loading`, `analysis`, `fixLoading`, `fixResult`.

On Run: `analyzeCsv(file, targetCol)` → set `analysis`, clear `fixResult`.

On Fix: `fixImbalance(file, analysis.target_col || targetCol)` → set `fixResult`.

Layout when `file` is set:

```jsx
<div className="layout fade-in">
  <div>
    <UploadPanel ... onRun={runAnalyze} loading={loading} />
    {analysis && (
      <>
        <OverviewStrip overview={analysis.overview} />
        <PreviewTable columns={analysis.columns} rows={analysis.preview_rows} />
        <IssuesList issues={analysis.issues} />
      </>
    )}
  </div>
  <div>
    {analysis && <ScorePanel score={analysis.score} />}
    <FixPanel
      visible={Boolean(analysis?.has_class_imbalance)}
      loading={fixLoading}
      onFix={runFix}
      result={fixResult}
    />
  </div>
</div>
```

Normalize API errors: if `detail` is an array (FastAPI validation), join messages into a string for `ErrorBanner`.

- [ ] **Step 3: End-to-end manual test**

Terminal 1:

```bash
cd /Users/kashishphulwani/Documents/machine_learning/AI_ready
uvicorn backend.main:app --reload --port 8000
```

Terminal 2:

```bash
cd frontend && npm run dev
```

Create demo CSV:

```bash
python3 -c "import pandas as pd; pd.DataFrame({'x':range(20),'y':[0]*18+[1]*2}).to_csv('/tmp/imbalanced_demo.csv', index=False)"
```

Checklist:

1. Open `http://localhost:5173`  
2. Upload `/tmp/imbalanced_demo.csv`, select target `y`, Run → score + issues + Fix visible  
3. Fix → before/after + download  
4. Upload balanced 5/5 CSV → Fix hidden  
5. Narrow viewport → columns stack  

- [ ] **Step 4: Commit (if git exists)**

```bash
git add frontend/src
git commit -m "$(cat <<'EOF'
Wire analyze/fix UI for terminal report layout.

EOF
)"
```

---

### Task 6: Spec checklist + polish

**Files:** none required unless gaps found

- [ ] **Step 1: Spec coverage**

Confirm against `docs/superpowers/specs/2026-07-11-vite-fastapi-terminal-ui-design.md`:

- [ ] Terminal colors / typography  
- [ ] Two-column layout + mobile stack  
- [ ] `/api/analyze` + `/api/fix` shapes  
- [ ] Fix only when `has_class_imbalance`  
- [ ] Download rebalanced CSV  
- [ ] Streamlit `app.py` untouched  
- [ ] `synthetic_rebalance.py` untouched  
- [ ] CORS + Vite proxy  
- [ ] 2–3 motions (fade-in / slide-up / button)  

- [ ] **Step 2: Re-run backend tests**

```bash
python3 -m pytest backend/tests -v
```

Expected: PASS

---

## Self-review (plan vs spec)

| Spec item | Task |
|-----------|------|
| `backend/quality.py` extraction | Task 1 |
| FastAPI analyze/fix + CORS | Task 2 |
| Vite React scaffold + proxy | Task 3 |
| Terminal theme + upload | Task 4 |
| Report layout + Fix + download | Task 5 |
| Manual + automated verification | Tasks 2, 5, 6 |

No TBD placeholders. API field names match the spec (`has_class_imbalance`, `rebalanced_csv`, `score_before` / `score_after`).
