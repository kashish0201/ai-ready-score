export default function UploadPanel({
  fileName,
  targetCandidates,
  targetCol,
  onTargetChange,
  onFile,
  onRun,
  loading,
}) {
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
        <button type="button" onClick={onRun} disabled={!fileName || loading}>
          {loading ? "Loading…" : "Run analysis"}
        </button>
      </div>
      {fileName && targetCandidates.length === 0 && (
        <p className="target-empty-message">
          No classification targets detected. This tool currently supports
          classification tasks.
        </p>
      )}
      <p className="muted" style={{ marginTop: "0.55rem", marginBottom: 0 }}>
        Target options are categorical-ish columns (≤20 unique values). Changing
        the target resets applied fixes.
      </p>
    </section>
  );
}
