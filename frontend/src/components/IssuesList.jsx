export default function IssuesList({ issues }) {
  if (!issues) return null;
  return (
    <section className="panel fade-in">
      <div className="panel-label">
        issues {issues.length ? `// ${issues.length} found` : "// none"}
      </div>
      {issues.length === 0 ? (
        <p className="muted">No major issues found.</p>
      ) : (
        issues.map((issue, i) => (
          <div key={`${issue.check}-${issue.column}-${i}`} className={`issue ${issue.severity}`}>
            <div className="issue-meta">
              {String(issue.severity).toUpperCase()} · {issue.check} · {issue.column}
            </div>
            <div>{issue.explanation}</div>
            <div className="muted" style={{ marginTop: "0.35rem" }}>
              {issue.recommendation}
            </div>
          </div>
        ))
      )}
    </section>
  );
}
