import { SEVERITY_CLASS } from "../lib/colors";

export function AnomalyBadge({ severity }: { severity: string }) {
  const cls = SEVERITY_CLASS[severity] ?? SEVERITY_CLASS.INFO;
  return (
    <span className={`inline-block rounded border px-2 py-0.5 text-xs font-semibold ${cls}`}>
      {severity}
    </span>
  );
}
