const FIX_LABELS = {
  missing_values: "Fill in missing values",
  duplicate_rows: "Remove duplicate rows",
  high_cardinality: "Drop identifier-like columns",
  constant_column: "Drop single-value columns",
  near_constant_column: "Drop near-constant columns",
  high_correlation: "Drop redundant correlated columns",
  numeric_outliers: "Cap extreme values",
  mixed_casing: "Standardise text casing",
  class_imbalance: "Generate synthetic rows to balance classes",
};

const VERDICT_ORDER = { safe: 0, review: 1, destructive: 2 };

const SAFE_CAPTION =
  '"No measurable cost" means no statistical distortion was detected. These metrics cannot detect semantic damage — e.g. capping latitude/longitude keeps the statistics tidy while moving stations to places they never were.';

export { FIX_LABELS };

export default function FixCards({
  previews,
  loading,
  busy,
  targetRatio,
  onTargetRatioChange,
  onApply,
  previewLoading,
}) {
  if (loading || previewLoading) {
    return (
      <section className="panel fade-in">
        <div className="panel-label">fix_previews</div>
        <p className="muted">
          Measuring the cost of each fix… class imbalance synthesis can take
          10–60 seconds on larger datasets.
        </p>
      </section>
    );
  }

  if (!previews) return null;

  const sorted = [...previews].sort((a, b) => {
    const va = VERDICT_ORDER[a.verdict] ?? 9;
    const vb = VERDICT_ORDER[b.verdict] ?? 9;
    if (va !== vb) return va - vb;
    return (b.score_delta || 0) - (a.score_delta || 0);
  });

  return (
    <section className="panel fade-in">
      <div className="panel-label">fix_previews</div>
      <p className="honesty-callout">
        The score measures the absence of detected issues, not truth. Every fix
        trades one property for another — a higher score can mean less honest
        data. Read the costs before applying.
      </p>

      {sorted.length === 0 ? (
        <p className="muted" style={{ marginTop: "0.85rem" }}>
          No further fixes available — the remaining issues have no automated
          fix, or the data is clean.
        </p>
      ) : (
        <div className="fix-cards">
          {sorted.map((preview) => (
            <FixCard
              key={preview.fix}
              preview={preview}
              busy={busy}
              targetRatio={targetRatio}
              onTargetRatioChange={onTargetRatioChange}
              onApply={onApply}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function FixCard({ preview, busy, targetRatio, onTargetRatioChange, onApply }) {
  if (preview.error) {
    return (
      <article className="fix-card verdict-review">
        <div className="fix-card-header">
          <h3>{FIX_LABELS[preview.fix] || preview.fix}</h3>
          <span className="verdict-badge review">error</span>
        </div>
        <p className="warn-text">{preview.error}</p>
      </article>
    );
  }

  const verdict = preview.verdict || "review";
  const warnings = preview.warnings || [];
  const creates = preview.creates_new_issues || [];
  const resolves = preview.resolves || [];
  const delta = preview.score_delta ?? 0;
  const deltaSign = delta > 0 ? "+" : "";

  return (
    <article className={`fix-card verdict-${verdict}`}>
      <div className="fix-card-header">
        <h3>{FIX_LABELS[preview.fix] || preview.fix}</h3>
        <span className={`verdict-badge ${verdict}`}>{verdict}</span>
      </div>

      {preview.action && <p className="muted fix-action">{preview.action}</p>}

      <div className="fix-gain">
        <div className="metric">
          <span>score</span>
          {preview.score_before} → {preview.score_after}{" "}
          <strong>
            ({deltaSign}
            {delta})
          </strong>
        </div>
        {resolves.length > 0 && (
          <div className="metric">
            <span>resolves</span>
            {resolves.join(", ")}
          </div>
        )}
      </div>

      {Array.isArray(preview.protected) && preview.protected.length > 0 && (
        <p className="protected-note">
          Protected:{" "}
          {preview.protected.map((p) => p.column).filter(Boolean).join(", ")}
          {" "}(
          {[...new Set(preview.protected.map((p) => p.tag).filter(Boolean))].join(
            ", ",
          ) || "tagged"}{" "}
          — this fix was skipped for these columns).
        </p>
      )}

      <div className={`fix-cost cost-${verdict}`}>
        <div className="panel-label">cost</div>
        {creates.length > 0 && (
          <p className="cost-creates">
            ⚠ This fix will create a new issue: {creates.join(", ")}
          </p>
        )}
        {warnings.length > 0 ? (
          <ul className="cost-warnings">
            {warnings.map((warning, i) => (
              <li key={`${preview.fix}-w-${i}`}>{warning}</li>
            ))}
          </ul>
        ) : verdict === "safe" ? (
          <>
            <p className="muted">No measurable cost detected</p>
            <p className="safe-caption">{SAFE_CAPTION}</p>
          </>
        ) : (
          <p className="muted">No warning strings returned for this fix.</p>
        )}
      </div>

      {preview.fix === "class_imbalance" && (
        <label className="ratio-slider">
          <span className="muted">
            Target majority:minority ratio ({Number(targetRatio).toFixed(1)})
          </span>
          <input
            type="range"
            min="1"
            max="5"
            step="0.1"
            value={targetRatio}
            onChange={(e) => onTargetRatioChange(Number(e.target.value))}
            disabled={busy}
          />
        </label>
      )}

      <button
        type="button"
        onClick={() => onApply(preview.fix)}
        disabled={busy}
      >
        {busy ? "Working…" : "Apply this fix"}
      </button>
    </article>
  );
}
