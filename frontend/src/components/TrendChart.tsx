import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { FCDayDetail } from "../api/types";

interface TrendChartProps {
  rows: FCDayDetail[];
  cm2Min: number;
  cm2Max: number;
}

export function TrendChart({ rows, cm2Min, cm2Max }: TrendChartProps) {
  const data = rows.map((r) => ({
    date: r.date.slice(5),
    cm1_pct: r.cm1_pct,
    cm2_pct: r.cm2_pct,
    color_code: r.color_code,
  }));

  return (
    <div className="h-72 w-full rounded-lg border border-gray-200 bg-white p-3">
      <h3 className="mb-2 text-sm font-semibold text-gray-700">Margin Trend</h3>
      <ResponsiveContainer width="100%" height="90%">
        <LineChart data={data} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} />
          <Tooltip
            formatter={(value, key) => [`${value}%`, key === "cm1_pct" ? "CM1" : "CM2"]}
            labelFormatter={(label) => `Date: ${label}`}
          />
          <Legend />
          <ReferenceArea y1={cm2Min} y2={cm2Max} fill="#22C55E" fillOpacity={0.08} />
          <ReferenceLine y={12} stroke="#EF4444" strokeDasharray="4 4" label={{ value: "12%", fontSize: 10, position: "insideTopLeft" }} />
          <ReferenceLine y={33} stroke="#3B82F6" strokeDasharray="4 4" label={{ value: "33%", fontSize: 10, position: "insideTopLeft" }} />
          <Line type="monotone" dataKey="cm1_pct" name="CM1%" stroke="#6366F1" dot={false} strokeWidth={2} />
          <Line type="monotone" dataKey="cm2_pct" name="CM2%" stroke="#0EA5E9" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
