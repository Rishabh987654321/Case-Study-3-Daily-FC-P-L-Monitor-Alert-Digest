import { useNavigate } from "react-router-dom";
import type { ColorCode, DashboardData } from "../api/types";
import { COLOR_BG_CLASS } from "../lib/colors";

interface ColorGridProps {
  uploadId: string;
  data: DashboardData;
  visibleFcs: string[];
  visibleColors: Set<ColorCode>;
}

export function ColorGrid({ uploadId, data, visibleFcs, visibleColors }: ColorGridProps) {
  const navigate = useNavigate();

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
      <table className="min-w-full border-collapse text-sm">
        <thead>
          <tr>
            <th className="sticky left-0 z-10 bg-gray-50 px-3 py-2 text-left font-semibold text-gray-700">
              FC
            </th>
            {data.dates.map((date) => (
              <th
                key={date}
                className="min-w-[56px] border-l border-gray-100 px-1 py-2 text-center text-xs font-medium text-gray-500"
              >
                {date.slice(5)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visibleFcs.map((fc) => {
            const byDate = new Map(data.grid[fc]?.map((d) => [d.date, d]));
            return (
              <tr key={fc} className="border-t border-gray-100">
                <td className="sticky left-0 z-10 bg-white px-3 py-1.5 font-medium whitespace-nowrap text-gray-800">
                  {fc}
                </td>
                {data.dates.map((date) => {
                  const cell = byDate.get(date);
                  if (!cell) {
                    return (
                      <td key={date} className="border-l border-gray-100 bg-gray-50 p-0.5">
                        <div className="flex h-10 w-full items-center justify-center text-gray-300">
                          —
                        </div>
                      </td>
                    );
                  }
                  const dimmed = !visibleColors.has(cell.color_code);
                  return (
                    <td key={date} className="border-l border-gray-100 p-0.5">
                      <button
                        type="button"
                        title={`${fc} — ${date}: CM2 = ${cell.cm2_pct}%, ${cell.anomaly_count} anomalies`}
                        onClick={() => navigate(`/dashboard/${uploadId}/fc/${encodeURIComponent(fc)}`)}
                        className={`flex h-10 w-full flex-col items-center justify-center rounded text-[11px] font-semibold text-white transition-transform hover:scale-105 ${
                          dimmed ? "bg-gray-200 text-gray-400" : COLOR_BG_CLASS[cell.color_code]
                        }`}
                      >
                        {cell.cm2_pct}%
                      </button>
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
