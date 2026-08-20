export default function UploadPanel({
  fileName,
  targetCandidates,
  targetCol,
  needsTarget,
  hasAnalysis,
  onTargetChange,
  onFile,
  onRun,
  loading,
}) {
  const runLabel = loading
    ? "Loading…"
    : needsTarget
      ? "Score with target"
      : "Update analysis";

  const runDisabled = !fileName || loading || (needsTarget && !targetCol);

  return (
    <section className="panel upload-panel">
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
        <div className="target-field">
          <label htmlFor="target-column">Target Column (classification)</label>
          <select
            id="target-column"
            value={targetCol || ""}
            onChange={(e) => onTargetChange(e.target.value || null)}
            disabled={!targetCandidates.length}
          >
            <option value="">None</option>
            {targetCandidates.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
        <button type="button" onClick={onRun} disabled={runDisabled}>
          {runLabel}
        </button>
      </div>
      {fileName && targetCandidates.length === 0 && (
        <p className="target-empty-message">
          No classification targets detected. This tool currently supports
          classification tasks.
        </p>
      )}
      <p className="muted" style={{ marginTop: "0.55rem", marginBottom: 0 }}>
        {hasAnalysis && needsTarget
          ? "Data quality checks ran on upload. Select a target for class imbalance and your full readiness score."
          : "Target options are categorical-ish columns (≤20 unique values). Changing the target resets applied fixes."}
      </p>
    </section>
  );
}
