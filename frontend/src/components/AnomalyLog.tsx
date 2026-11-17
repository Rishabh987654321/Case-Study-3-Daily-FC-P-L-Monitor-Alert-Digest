import { useMemo, useState } from "react";
import type { AnomalyLogEntry } from "../api/types";
import { AnomalyBadge } from "./AnomalyBadge";

type SortKey = "date" | "line_item" | "actual_pct" | "deviation" | "status" | "severity";

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: "date", label: "Date" },
  { key: "line_item", label: "Line Item" },
  { key: "actual_pct", label: "Actual%" },
  { key: "deviation", label: "Deviation" },
  { key: "status", label: "Status" },
  { key: "severity", label: "Severity" },
];

export function AnomalyLog({ anomalies }: { anomalies: AnomalyLogEntry[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("date");
  const [sortDir, setSortDir] = useState<1 | -1>(1);

  const sorted = useMemo(() => {
    const copy = [...anomalies];
    copy.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * sortDir;
      return String(av).localeCompare(String(bv)) * sortDir;
    });
    return copy;
  }, [anomalies, sortKey, sortDir]);

  function handleSort(key: SortKey) {
    if (key === sortKey) setSortDir((d) => (d === 1 ? -1 : 1));
    else {
      setSortKey(key);
      setSortDir(1);
    }
  }

  if (anomalies.length === 0) {
    return <p className="text-sm text-gray-500">No anomalies for this FC.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50 text-left text-xs font-semibold text-gray-500 uppercase">
          <tr>
            {COLUMNS.map((c) => (
              <th
                key={c.key}
                onClick={() => handleSort(c.key)}
                className="cursor-pointer px-3 py-2 select-none hover:text-gray-700"
              >
                {c.label}
                {sortKey === c.key && (sortDir === 1 ? " ▲" : " ▼")}
              </th>
            ))}
            <th className="px-3 py-2">Target Range</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((a, i) => (
            <tr key={i} className="border-t border-gray-100">
              <td className="px-3 py-2 whitespace-nowrap text-gray-700">{a.date}</td>
              <td className="px-3 py-2 text-gray-700">{a.line_item}</td>
              <td className="px-3 py-2 text-gray-700">{a.actual_pct}%</td>
              <td className="px-3 py-2 text-gray-700">
                {a.deviation > 0 ? "+" : ""}
                {a.deviation}pp
              </td>
              <td className="px-3 py-2 text-gray-500">{a.status}</td>
              <td className="px-3 py-2">
                <AnomalyBadge severity={a.severity} />
              </td>
              <td className="px-3 py-2 text-gray-500">{a.target_range}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
