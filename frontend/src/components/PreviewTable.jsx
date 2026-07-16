export default function PreviewTable({ columns, rows }) {
  if (!rows?.length) return null;
  const cols = columns?.length ? columns : Object.keys(rows[0] || {});
  return (
    <section className="panel fade-in">
      <div className="panel-label">dataset_preview</div>
      <div className="preview-wrap">
        <table className="preview-table">
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                {cols.map((c) => (
                  <td key={c}>{row[c] == null ? "—" : String(row[c])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
