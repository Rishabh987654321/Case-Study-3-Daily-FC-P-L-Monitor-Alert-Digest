import { useState } from "react";

export function InsightBox({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(true);

  if (!text) return null;

  return (
    <div className="rounded-md border border-indigo-200 bg-indigo-50 p-3 text-sm text-indigo-900">
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="mb-1 flex w-full items-center justify-between font-semibold"
      >
        <span>Insight</span>
        <span className="text-indigo-500">{expanded ? "▲" : "▼"}</span>
      </button>
      {expanded && <p className="leading-relaxed">{text}</p>}
    </div>
  );
}
