const TAG_OPTIONS = [
  { value: "", label: "untagged" },
  { value: "identifier", label: "identifier" },
  { value: "geographic", label: "geographic" },
  { value: "temporal", label: "temporal" },
  { value: "categorical_code", label: "categorical_code" },
  { value: "monetary", label: "monetary" },
  { value: "free_text", label: "free_text" },
];

export default function TagsPanel({
  columns,
  proposed,
  draft,
  onChange,
  onSave,
  saving,
  savedAt,
}) {
  const rows = (columns || []).map((column) => {
    const proposal = proposed?.[column];
    return {
      column,
      proposal,
      value: draft?.[column] ?? "",
    };
  });

  const proposedCount = Object.keys(proposed || {}).length;

  return (
    <section className="panel fade-in">
      <div className="panel-label">semantic_tags</div>
      <p className="muted" style={{ marginTop: 0 }}>
        We propose tags from the data. Confirm or correct them — fixes will
        respect your choices and skip columns where a fix doesn&apos;t make sense.
      </p>
      <p className="muted">
        {proposedCount
          ? `${proposedCount} column(s) have strong evidence for a tag.`
          : "No strong tag proposals — you can still tag columns manually."}
      </p>

      <div className="tags-table-wrap">
        <table className="tags-table">
          <thead>
            <tr>
              <th>column</th>
              <th>tag</th>
              <th>evidence</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ column, proposal, value }) => (
              <tr key={column} className={proposal ? "has-proposal" : ""}>
                <td className="tag-col-name">{column}</td>
                <td>
                  <select
                    value={value}
                    onChange={(e) => onChange(column, e.target.value)}
                    disabled={saving}
                  >
                    {TAG_OPTIONS.map((opt) => (
                      <option key={opt.value || "untagged"} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  {proposal ? (
                    <div className="tag-evidence">
                      <span className={`confidence-badge ${proposal.confidence}`}>
                        {proposal.confidence}
                      </span>
                      <span className="muted">{proposal.reason}</span>
                    </div>
                  ) : (
                    <span className="muted">untagged — no strong signal</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="row" style={{ marginTop: "0.85rem" }}>
        <button type="button" onClick={onSave} disabled={saving}>
          {saving ? "Saving…" : "Save tags"}
        </button>
        {savedAt && (
          <span className="muted saved-note">Tags saved — fixes will use them.</span>
        )}
      </div>
    </section>
  );
}
