import { FIX_LABELS } from "./FixCards";

export default function ProgressPanel({
  score,
  originalScore,
  roundNum,
  history,
  busy,
  onReset,
  onDownload,
}) {
  if (!score) return null;

  const original = originalScore?.score ?? "—";

  return (
    <section className="panel score-panel fade-in">
      <div className="panel-label">progress // round {roundNum}</div>
      <div className="score-number">{score.score}</div>
      <div className="score-grade">{score.grade}</div>
      <div className="metrics" style={{ marginTop: "0.85rem", textAlign: "left" }}>
        <div className="metric">
          <span>current</span>
          {score.score}/100
        </div>
        <div className="metric">
          <span>original</span>
          {original}/100
        </div>
        <div className="metric">
          <span>high</span>
          {score.high_issues}
        </div>
        <div className="metric">
          <span>medium</span>
          {score.medium_issues}
        </div>
        <div className="metric">
          <span>low</span>
          {score.low_issues}
        </div>
      </div>
      <p className="score-summary">{score.summary}</p>

      {history?.length > 0 && (
        <div className="history-wrap">
          <div className="panel-label">history</div>
          <table className="history-table">
            <thead>
              <tr>
                <th>round</th>
                <th>fix</th>
                <th>score</th>
              </tr>
            </thead>
            <tbody>
              {history.map((row) => (
                <tr key={`${row.round}-${row.fix}`}>
                  <td>{row.round}</td>
                  <td>{FIX_LABELS[row.fix] || row.fix}</td>
                  <td>
                    {row.score_before} → {row.score_after}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="row" style={{ marginTop: "0.85rem" }}>
        <button type="button" onClick={onReset} disabled={busy}>
          Reset to original
        </button>
        <button type="button" onClick={onDownload} disabled={busy}>
          Download fixed CSV
        </button>
      </div>
    </section>
  );
}
