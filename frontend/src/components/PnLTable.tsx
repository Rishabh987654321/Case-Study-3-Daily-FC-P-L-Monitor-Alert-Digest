import { Fragment, useState } from "react";
import type { FCDayDetail } from "../api/types";
import { ColorBadge } from "./ColorBadge";
import { AnomalyBadge } from "./AnomalyBadge";
import { InsightBox } from "./InsightBox";

const PCT_COLUMNS: { key: keyof FCDayDetail; label: string; lineItem: string }[] = [
  { key: "manpower_pct", label: "Manpower%", lineItem: "Manpower Cost" },
  { key: "packaging_pct", label: "Packaging%", lineItem: "Packaging Cost" },
  { key: "power_fuel_pct", label: "Power%", lineItem: "Power & Fuel" },
  { key: "fc_rent_pct", label: "Rent%", lineItem: "FC Rent" },
  { key: "equipment_pct", label: "Equipment%", lineItem: "Equipment Rentals" },
  { key: "overheads_pct", label: "Overheads%", lineItem: "Overheads" },
];

export function PnLTable({ rows }: { rows: FCDayDetail[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50 text-left text-xs font-semibold text-gray-500 uppercase">
          <tr>
            <th className="px-3 py-2">Date</th>
            <th className="px-3 py-2">Revenue</th>
            {PCT_COLUMNS.map((c) => (
              <th key={c.key} className="px-3 py-2">
                {c.label}
              </th>
            ))}
            <th className="px-3 py-2">CM1%</th>
            <th className="px-3 py-2">CM2%</th>
            <th className="px-3 py-2">Color</th>
            <th className="px-3 py-2">Anomalies</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const breachedItems = new Set(r.anomalies.map((a) => a.line_item));
            const isExpanded = expanded === r.id;
            return (
              <Fragment key={r.id}>
                <tr
                  onClick={() => setExpanded(isExpanded ? null : r.id)}
                  className="cursor-pointer border-t border-gray-100 hover:bg-gray-50"
                >
                  <td className="px-3 py-2 whitespace-nowrap text-gray-700">{r.date}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-gray-700">
                    ₹{r.revenue.toLocaleString()}
                  </td>
                  {PCT_COLUMNS.map((c) => {
                    const breached = breachedItems.has(c.lineItem);
                    return (
                      <td
                        key={c.key}
                        className={`px-3 py-2 ${breached ? "bg-orange-50 font-medium text-orange-700" : "text-gray-600"}`}
                      >
                        {r[c.key] as number}%
                      </td>
                    );
                  })}
                  <td className="px-3 py-2 text-gray-700">{r.cm1_pct}%</td>
                  <td className="px-3 py-2 font-medium text-gray-900">{r.cm2_pct}%</td>
                  <td className="px-3 py-2">
                    <ColorBadge color={r.color_code} size="sm" />
                  </td>
                  <td className="px-3 py-2 text-gray-500">{r.anomalies.length}</td>
                </tr>
                {isExpanded && (
                  <tr className="border-t border-gray-100 bg-gray-50">
                    <td colSpan={11} className="px-4 py-4">
                      <div className="space-y-3">
                        <InsightBox text={r.insight} />
                        {r.anomalies.length > 0 && (
                          <div>
                            <p className="mb-1 text-xs font-semibold text-gray-500 uppercase">
                              Anomalies
                            </p>
                            <ul className="space-y-1">
                              {r.anomalies.map((a, i) => (
                                <li key={i} className="flex items-center gap-2 text-sm text-gray-700">
                                  <AnomalyBadge severity={a.severity} />
                                  <span>
                                    {a.line_item}: {a.actual_pct}% (target {a.target_min}–{a.target_max}%,
                                    deviation {a.deviation > 0 ? "+" : ""}
                                    {a.deviation}pp)
                                  </span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
