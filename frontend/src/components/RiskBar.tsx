export function RiskBar({ value, label }: { value: number; label: string }) {
  return (
    <div className="risk-bar">
      <span className="risk-bar__label">{label}</span>
      <progress max="100" value={Math.max(0, Math.min(100, value))} aria-label={`${label}: ${value.toFixed(1)}`} />
      <span className="risk-bar__value">{value.toFixed(1)}</span>
    </div>
  );
}
