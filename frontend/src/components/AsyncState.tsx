import { AlertTriangle, Database } from "lucide-react";

export function LoadingState({ label }: { label: string }) {
  return (
    <div className="state-panel" role="status" aria-live="polite" aria-busy="true">
      <span className="loading-bar" aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="state-panel" role="status">
      <Database aria-hidden="true" />
      <h2>{title}</h2>
      <p>{detail}</p>
    </div>
  );
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="state-panel state-panel--error" role="alert">
      <AlertTriangle aria-hidden="true" />
      <h2>Unable to load this view</h2>
      <p>{message}</p>
      {retry && (
        <button className="button button--secondary" type="button" onClick={retry}>
          Try again
        </button>
      )}
    </div>
  );
}
