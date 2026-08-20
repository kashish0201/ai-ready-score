import { useEffect, useRef, useState } from "react";
import "./styles.css";
import Hero from "./components/Hero";
import ErrorBanner from "./components/ErrorBanner";
import UploadPanel from "./components/UploadPanel";
import OverviewStrip from "./components/OverviewStrip";
import PreviewTable from "./components/PreviewTable";
import IssuesList from "./components/IssuesList";
import ProgressPanel from "./components/ProgressPanel";
import FixCards from "./components/FixCards";
import TagsPanel from "./components/TagsPanel";
import TabBar from "./components/TabBar";
import {
  applyDatasetFix,
  downloadDatasetCsv,
  getDatasetPreview,
  getDatasetTags,
  resetDataset,
  saveDatasetTags,
  setDatasetTarget,
  uploadDataset,
} from "./api";

function draftFromTagsResponse(columns, proposed, confirmed) {
  const draft = {};
  for (const col of columns || []) {
    if (confirmed?.[col]) draft[col] = confirmed[col];
    else if (proposed?.[col]?.tag) draft[col] = proposed[col].tag;
    else draft[col] = "";
  }
  return draft;
}

export default function App() {
  const [fileName, setFileName] = useState(null);
  const [datasetId, setDatasetId] = useState(null);
  const [targetCandidates, setTargetCandidates] = useState([]);
  const [targetCol, setTargetCol] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [scoreState, setScoreState] = useState(null);
  const [previews, setPreviews] = useState(null);
  const [previewError, setPreviewError] = useState(null);
  const [targetRatio, setTargetRatio] = useState(1.5);
  const [activeTab, setActiveTab] = useState("dataset");
  const [proposedTags, setProposedTags] = useState({});
  const [tagDraft, setTagDraft] = useState({});
  const [tagsSaving, setTagsSaving] = useState(false);
  const [tagsSavedAt, setTagsSavedAt] = useState(null);
  const ratioTimer = useRef(null);
  const ratioTouched = useRef(false);
  const previewRequestId = useRef(0);

  function applyScore(body) {
    setScoreState(body);
    if (body.previews) setPreviews(body.previews);
  }

  async function loadPreviews() {
    if (!datasetId) return;
    const requestId = ++previewRequestId.current;
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const preview = await getDatasetPreview(datasetId, { targetRatio });
      if (requestId !== previewRequestId.current) return;
      setPreviews(preview.previews || []);
    } catch (err) {
      if (requestId !== previewRequestId.current) return;
      setPreviewError(err.message);
      setPreviews([]);
    } finally {
      if (requestId === previewRequestId.current) {
        setPreviewLoading(false);
      }
    }
  }

  async function refreshClassImbalancePreview() {
    if (!datasetId) return;
    const requestId = ++previewRequestId.current;
    setPreviewLoading(true);
    try {
      const preview = await getDatasetPreview(datasetId, {
        targetRatio,
        selected: "class_imbalance",
      });
      if (requestId !== previewRequestId.current) return;
      setPreviews((prev) => {
        const others = (prev || []).filter((p) => p.fix !== "class_imbalance");
        return [...others, ...(preview.previews || [])];
      });
    } catch {
      // Imbalance may no longer apply after other fixes
    } finally {
      if (requestId === previewRequestId.current) {
        setPreviewLoading(false);
      }
    }
  }

  async function loadTags(id, columns) {
    const body = await getDatasetTags(id);
    setProposedTags(body.proposed || {});
    setTagDraft(
      draftFromTagsResponse(columns, body.proposed || {}, body.confirmed || {}),
    );
    return body;
  }

  async function handleFile(next) {
    setError(null);
    setScoreState(null);
    setPreviews(null);
    setPreviewError(null);
    setTargetCol(null);
    setDatasetId(null);
    setFileName(null);
    setTargetCandidates([]);
    setProposedTags({});
    setTagDraft({});
    setTagsSavedAt(null);
    setActiveTab("dataset");
    ratioTouched.current = false;
    if (!next) return;

    setLoading(true);
    try {
      const body = await uploadDataset(next);
      setDatasetId(body.dataset_id);
      setFileName(body.filename || next.name);
      setTargetCandidates(body.target_candidates || []);
      applyScore(body);
      await loadTags(body.dataset_id, body.columns);
      setActiveTab("dataset");
      loadPreviews();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function runAnalyze() {
    if (!datasetId) return;
    setLoading(true);
    setError(null);
    setPreviews(null);
    setPreviewError(null);
    ratioTouched.current = false;
    previewRequestId.current += 1;
    try {
      const scored = await setDatasetTarget(datasetId, targetCol);
      applyScore(scored);
      setTargetCol(scored.target_col ?? targetCol);
      await loadTags(datasetId, scored.columns);
      setActiveTab("score");
    } catch (err) {
      setError(err.message);
      setPreviews(null);
      setPreviewError(null);
    } finally {
      setLoading(false);
    }
    loadPreviews();
  }

  async function handleSaveTags() {
    if (!datasetId) return;
    setTagsSaving(true);
    setError(null);
    try {
      const tags = {};
      for (const [col, value] of Object.entries(tagDraft)) {
        if (value) tags[col] = value;
      }
      await saveDatasetTags(datasetId, tags);
      setTagsSavedAt(Date.now());
      if (scoreState?.score != null) {
        loadPreviews();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setTagsSaving(false);
    }
  }

  function handleTagChange(column, value) {
    setTagDraft((prev) => ({ ...prev, [column]: value }));
    setTagsSavedAt(null);
  }

  async function handleApply(fixName) {
    if (!datasetId) return;
    setBusy(true);
    setError(null);
    try {
      const body = await applyDatasetFix(datasetId, {
        fix: fixName,
        targetRatio,
      });
      applyScore(body);
      setPreviews(body.previews || []);
      setActiveTab("score");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleReset() {
    if (!datasetId) return;
    setBusy(true);
    setError(null);
    setPreviews(null);
    setPreviewError(null);
    ratioTouched.current = false;
    previewRequestId.current += 1;
    try {
      const scored = await resetDataset(datasetId);
      applyScore(scored);
      await loadTags(datasetId, scored.columns);
      setActiveTab("score");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
    loadPreviews();
  }

  async function handleDownload() {
    if (!datasetId) return;
    try {
      const blob = await downloadDatasetCsv(datasetId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "fixed_dataset.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    }
  }

  function handleTargetRatioChange(value) {
    ratioTouched.current = true;
    setTargetRatio(value);
  }

  useEffect(() => {
    if (!ratioTouched.current || !datasetId) return;

    if (ratioTimer.current) clearTimeout(ratioTimer.current);
    ratioTimer.current = setTimeout(() => {
      refreshClassImbalancePreview();
    }, 500);

    return () => {
      if (ratioTimer.current) clearTimeout(ratioTimer.current);
    };
  }, [targetRatio, datasetId]);

  const hasAnalysis = Boolean(scoreState?.score != null);
  const needsTarget = Boolean(scoreState?.needs_target);
  const issueCount = scoreState?.issues?.length ?? 0;
  const fixCount = previews?.length ?? 0;
  const confirmedTagCount = Object.values(tagDraft).filter(Boolean).length;

  const tabs = [
    { id: "dataset", label: "Dataset" },
    {
      id: "tags",
      label: "Tags",
      badge: datasetId ? confirmedTagCount : null,
      disabled: !datasetId,
    },
    {
      id: "issues",
      label: "Issues",
      badge: hasAnalysis ? issueCount : null,
      disabled: !hasAnalysis,
    },
    {
      id: "fixes",
      label: "Fixes",
      badge: hasAnalysis ? (previewLoading ? "…" : fixCount) : null,
      disabled: !hasAnalysis,
    },
    {
      id: "score",
      label: "Score",
      badge: hasAnalysis ? scoreState.score : null,
      disabled: !hasAnalysis,
    },
  ];

  return (
    <div className="app-shell">
      <Hero />
      <ErrorBanner message={error} />

      <main className="workspace fade-in">
        <UploadPanel
          fileName={fileName}
          targetCandidates={targetCandidates}
          targetCol={targetCol}
          needsTarget={needsTarget}
          hasAnalysis={hasAnalysis}
          onTargetChange={setTargetCol}
          onFile={handleFile}
          onRun={runAnalyze}
          loading={loading || busy}
        />

        {datasetId && scoreState && (
          <>
            <TabBar tabs={tabs} active={activeTab} onChange={setActiveTab} />

            <div className="tab-panel">
              {activeTab === "dataset" && (
                <>
                  <OverviewStrip overview={scoreState.overview} />
                  <PreviewTable
                    columns={scoreState.columns}
                    rows={scoreState.preview_rows}
                  />
                  {needsTarget && (
                    <p className="muted tab-hint">
                      Data quality checks ran on upload. Pick a target column
                      above and click Score with target to check class imbalance
                      and get your full readiness score.
                    </p>
                  )}
                </>
              )}

              {activeTab === "tags" && (
                <TagsPanel
                  columns={scoreState.columns}
                  proposed={proposedTags}
                  draft={tagDraft}
                  onChange={handleTagChange}
                  onSave={handleSaveTags}
                  saving={tagsSaving}
                  savedAt={tagsSavedAt}
                />
              )}

              {activeTab === "issues" && hasAnalysis && (
                <IssuesList issues={scoreState.issues} />
              )}

              {activeTab === "fixes" && hasAnalysis && (
                <FixCards
                  previews={previews}
                  loading={loading}
                  previewLoading={previewLoading}
                  previewError={previewError}
                  busy={busy || loading || previewLoading}
                  targetRatio={targetRatio}
                  onTargetRatioChange={handleTargetRatioChange}
                  onApply={handleApply}
                />
              )}

              {activeTab === "score" && hasAnalysis && (
                <div className="score-tab">
                  <ProgressPanel
                    score={scoreState}
                    originalScore={scoreState.original_score}
                    roundNum={scoreState.round_num}
                    history={scoreState.history}
                    needsTarget={needsTarget}
                    busy={busy || loading || previewLoading}
                    onReset={handleReset}
                    onDownload={handleDownload}
                  />
                  {!needsTarget && (
                    <p className="muted tab-hint">
                      Review fix costs on the Fixes tab before applying — a
                      higher score can mean less honest data.
                    </p>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
