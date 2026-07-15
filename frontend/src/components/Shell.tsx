import {
  Beaker,
  ChartNoAxesCombined,
  Fingerprint,
  GitBranch,
  LayoutDashboard,
  ShieldCheck,
} from "lucide-react";
import type { ReactNode } from "react";

export type View = "overview" | "identities" | "paths" | "remediation" | "results";

const items = [
  { id: "overview" as const, label: "Overview", icon: LayoutDashboard },
  { id: "identities" as const, label: "Identities", icon: Fingerprint },
  { id: "paths" as const, label: "Paths", icon: GitBranch },
  { id: "remediation" as const, label: "Remediation", icon: ShieldCheck },
  { id: "results" as const, label: "Research results", icon: ChartNoAxesCombined },
];

export function Shell({
  view,
  onView,
  children,
}: {
  view: View;
  onView: (view: View) => void;
  children: ReactNode;
}) {
  return (
    <div className="app-shell">
      <aside className="rail">
        <div className="brand">
          <span className="brand-mark"><Beaker aria-hidden="true" /></span>
          <span><strong>GraphTrust</strong><small>Investigation console</small></span>
        </div>
        <nav aria-label="Primary navigation">
          {items.map(({ id, label, icon: Icon }) => (
            <button
              className={view === id ? "nav-item nav-item--active" : "nav-item"}
              type="button"
              aria-current={view === id ? "page" : undefined}
              onClick={() => onView(id)}
              key={id}
            >
              <Icon aria-hidden="true" />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        <p className="rail-note">Analysis is read-only. No live IAM changes are executed.</p>
      </aside>
      <main id="main-content" className="main-content">{children}</main>
    </div>
  );
}
