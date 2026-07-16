export default function OverviewStrip({ overview }) {
  if (!overview) return null;
  return (
    <section className="panel fade-in">
      <div className="panel-label">dataset_overview</div>
      <div className="metrics">
        <div className="metric">
          <span>rows</span>
          {overview.rows}
        </div>
        <div className="metric">
          <span>columns</span>
          {overview.columns}
        </div>
        <div className="metric">
          <span>missing</span>
          {Number(overview.missing_pct).toFixed(2)}%
        </div>
        <div className="metric">
          <span>numeric</span>
          {overview.numeric_columns}
        </div>
        <div className="metric">
          <span>categorical</span>
          {overview.categorical_columns}
        </div>
      </div>
    </section>
  );
}
