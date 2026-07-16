export default function TabBar({ tabs, active, onChange }) {
  return (
    <nav className="tab-bar" aria-label="Main sections">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className={`tab-btn${active === tab.id ? " active" : ""}`}
          onClick={() => onChange(tab.id)}
          disabled={tab.disabled}
        >
          {tab.label}
          {tab.badge != null && tab.badge !== "" && (
            <span className="tab-badge">{tab.badge}</span>
          )}
        </button>
      ))}
    </nav>
  );
}
