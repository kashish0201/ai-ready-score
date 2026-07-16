# Vite + FastAPI Terminal Report UI — Design Spec

**Date:** 2026-07-11  
**Status:** Approved for planning  
**Scope:** Replace the Streamlit-facing experience with a Vite React frontend and FastAPI backend, using the Terminal Report visual direction and a two-column report layout. Keep existing quality checks, scoring, and synthetic rebalance logic.

## Goal

Ship a polished, dark “terminal report” web app where users upload a CSV, get an AI-Ready Score with issues, and can Fix class imbalance via SDV — with full visual control via HTML/CSS/JS (React), not Streamlit.

## Decisions (from brainstorming)

| Decision | Choice |
|----------|--------|
| Visual direction | Terminal Report — charcoal background, monospace accents, green/amber/red status |
| Layout | Two-column report: workflow left, score + Fix panel right |
| Frontend stack | Vite + React + CSS (CSS variables) |
| Backend | FastAPI JSON APIs + CORS |
| Repo layout | Monorepo folders `frontend/` + `backend/` (not a separate git repo) |
| Streamlit `app.py` | Leave in place for now; do not delete |
| Rebalance module | `synthetic_rebalance.py` unchanged |
| Charts | CSS/SVG bars in the frontend (no matplotlib in the new UI) |

## Architecture

```
AI_ready/
  backend/
    main.py          # FastAPI app, routes, CORS, static optional
    quality.py       # quality checks + scoring (extracted from app.py)
    requirements.txt # fastapi, uvicorn, pandas, numpy, python-multipart, sdv
  frontend/
    package.json     # vite, react, react-dom
    vite.config.js   # proxy /api → http://localhost:8000
    index.html
    src/
      main.jsx
      App.jsx
      api.js
      styles.css
      components/    # Hero, UploadPanel, ScorePanel, IssuesList, FixPanel, etc.
  synthetic_rebalance.py
  app.py             # Streamlit (untouched in this project)
```

```
Browser (Vite :5173)
    │  multipart CSV + target
    ▼
FastAPI (:8000)
    ├── POST /api/analyze  → quality.py + score
    └── POST /api/fix     → rebalance_with_synthetic + re-score
```

## API

### `POST /api/analyze`

**Request:** `multipart/form-data`

| Field | Type | Required |
|-------|------|----------|
| `file` | CSV upload | yes |
| `target_col` | string | no (empty / omit = no target) |

**Response JSON (200):**

```json
{
  "columns": ["..."],
  "overview": {
    "rows": 0,
    "columns": 0,
    "missing_pct": 0.0,
    "numeric_columns": 0,
    "categorical_columns": 0,
    "datetime_columns": 0
  },
  "preview_rows": [{ "...": "..." }],
  "target_col": "y",
  "score": {
    "score": 82,
    "grade": "Good",
    "total_issues": 6,
    "high_issues": 2,
    "medium_issues": 3,
    "low_issues": 1,
    "summary": "..."
  },
  "issues": [
    {
      "check": "class_imbalance",
      "column": "y",
      "severity": "high",
      "metric": "imbalance_ratio",
      "value": 9.0,
      "explanation": "...",
      "recommendation": "..."
    }
  ],
  "has_class_imbalance": true
}
```

### `POST /api/fix`

**Request:** `multipart/form-data`

| Field | Type | Required |
|-------|------|----------|
| `file` | CSV upload (original) | yes |
| `target_col` | string | yes |

**Response JSON (200) on success:**

```json
{
  "report": {
    "status": "success",
    "minority_class": "1",
    "majority_class": "0",
    "rows_before": 20,
    "rows_after": 30,
    "synthetic_rows_added": 10,
    "ratio_before": 9.0,
    "ratio_after": 1.5,
    "target_ratio": 1.5
  },
  "score_before": { "score": 82, "grade": "Good", "...": "..." },
  "score_after": { "score": 90, "grade": "Excellent", "...": "..." },
  "issues_after": [],
  "rebalanced_csv": "col1,col2\\n..."
}
```

`rebalanced_csv` is a plain UTF-8 CSV string. Frontend builds a Blob download as `rebalanced_dataset.csv`.

**On skip/fail (`report.status` in `skipped`/`failed`):** still 200 with `report.reason` and `rebalanced_csv: null`. Frontend shows a warning.

**Errors:**

| Code | When |
|------|------|
| 400 | Unreadable CSV, empty file, Fix without `target_col` |
| 500 | Unexpected server/SDV failure with `{ "detail": "..." }` |

### Stateless backend

No long-term file storage. Frontend keeps the selected `File` in memory and re-sends it for Fix. Target dropdown columns come from a client-side header peek of the selected File (no `/api/columns` endpoint).

## UI

### Visual system

- Background: `#0b1220` page, panels `#111827`, borders `#1f2937`
- Accents: success/score `#34d399`, warn `#fbbf24`, danger `#f87171`, muted `#9ca3af`
- Typography: system UI for brand/headings; `ui-monospace` for labels, prompts, meta
- CSS variables in `styles.css`; avoid purple, cream/terracotta, newspaper layouts, emoji decoration, heavy glow
- Motion: fade-in for results panel; short slide-up for score card; button press feedback (2–3 intentional motions)

### Layout

1. **Top bar / hero:** `$ ai-ready check` prompt line + brand **AI-Ready Score** + one-line subtitle  
2. **After file selected — two columns:**
   - **Left (~60%):** upload dropzone, target select, Run analysis, dataset overview metrics, preview table, issues list  
   - **Right (~40%):** score panel (large number + grade + severity counts); Fix panel when `has_class_imbalance`  
3. **Fix panel:** explanation, Fix button, before→after metrics, download rebalanced CSV  
4. **Empty state:** hero + upload only until a file is chosen  

### Components (suggested)

| Component | Responsibility |
|-----------|----------------|
| `Hero` | Brand + prompt line |
| `UploadPanel` | Dropzone, file name, target select, Run |
| `OverviewStrip` | Row/column/missing metrics |
| `PreviewTable` | First N rows |
| `ScorePanel` | Score, grade, counts, summary |
| `IssuesList` | Severity-styled issue cards |
| `FixPanel` | Rebalance CTA + results + download |
| `ErrorBanner` | API / validation errors |

## Backend module extraction

`backend/quality.py` should contain (ported from `app.py`, Streamlit-free):

- All `check_*` functions  
- `run_quality_checks`  
- `compute_ai_ready_score`  
- `get_dataset_overview` (optional helper)

`backend/main.py` imports these plus `rebalance_with_synthetic` from project root (adjust `sys.path` or package layout so imports work when running uvicorn from repo root).

## Non-goals

- Deleting or redesigning Streamlit `app.py` in this iteration  
- Auth, multi-user sessions, cloud storage  
- Configurable `target_ratio` UI  
- Fixing non-imbalance issues  
- React Router multi-page app (single page is enough)  
- TypeScript (use JavaScript for v1)

## Runbook (dev)

```bash
# backend
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# run from repo root if imports need synthetic_rebalance:
# uvicorn backend.main:app --reload --port 8000

# frontend
cd frontend && npm install && npm run dev
```

Open Vite URL (typically `http://localhost:5173`).

## Manual test plan

1. Upload imbalanced CSV → select target → Run → score + issues appear; Fix panel visible  
2. Click Fix → before/after + download works; original file still the upload source  
3. Balanced target / no imbalance → Fix panel hidden  
4. Bad file / empty CSV → error banner, no crash  
5. Mobile width: columns stack; still usable  

## Files to create / change

| Path | Action |
|------|--------|
| `backend/quality.py` | Create — extract checks/scoring |
| `backend/main.py` | Create — FastAPI routes |
| `backend/requirements.txt` | Create |
| `frontend/*` | Create — Vite React app |
| `synthetic_rebalance.py` | No change |
| `app.py` | No change (this iteration) |
| `docs/superpowers/specs/2026-07-11-vite-fastapi-terminal-ui-design.md` | This document |
