import {
  Area,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  AreaChart,
} from "recharts";
import type { FCDayDetail } from "../api/types";

const SERIES: { key: keyof FCDayDetail; label: string; color: string }[] = [
  { key: "manpower_pct", label: "Manpower", color: "#6366F1" },
  { key: "packaging_pct", label: "Packaging", color: "#F59E0B" },
  { key: "power_fuel_pct", label: "Power & Fuel", color: "#10B981" },
  { key: "fc_rent_pct", label: "FC Rent", color: "#EF4444" },
  { key: "equipment_pct", label: "Equipment", color: "#8B5CF6" },
  { key: "overheads_pct", label: "Overheads", color: "#64748B" },
];

export function CostBreakdownChart({ rows }: { rows: FCDayDetail[] }) {
  const data = rows.map((r) => ({
    date: r.date.slice(5),
    manpower_pct: r.manpower_pct,
    packaging_pct: r.packaging_pct,
    power_fuel_pct: r.power_fuel_pct,
    fc_rent_pct: r.fc_rent_pct,
    equipment_pct: r.equipment_pct,
    overheads_pct: r.overheads_pct,
  }));

  return (
    <div className="h-72 w-full rounded-lg border border-gray-200 bg-white p-3">
      <h3 className="mb-2 text-sm font-semibold text-gray-700">Cost Breakdown (% of Revenue)</h3>
      <ResponsiveContainer width="100%" height="90%">
        <AreaChart data={data} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip formatter={(value) => `${value}%`} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {SERIES.map((s) => (
            <Area
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stackId="1"
              stroke={s.color}
              fill={s.color}
              fillOpacity={0.7}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
