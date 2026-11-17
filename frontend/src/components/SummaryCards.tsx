import type { ColorCode, DashboardData } from "../api/types";
import { COLOR_BG_CLASS, COLOR_LABEL } from "../lib/colors";

const ORDER: ColorCode[] = ["RED", "YELLOW", "GREEN", "BLUE"];
const EMOJI: Record<ColorCode, string> = { RED: "🔴", YELLOW: "🟡", GREEN: "🟢", BLUE: "🔵" };

export function SummaryCards({ data }: { data: DashboardData }) {
  const allCells = Object.values(data.grid).flat();
  const total = allCells.length || 1;
  const counts: Record<ColorCode, number> = { RED: 0, YELLOW: 0, GREEN: 0, BLUE: 0 };
  for (const cell of allCells) counts[cell.color_code]++;

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {ORDER.map((color) => (
        <div key={color} className="rounded-lg border border-gray-200 bg-white p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-gray-500">
            <span>{EMOJI[color]}</span>
            {COLOR_LABEL[color]} days
          </div>
          <div className="mt-1 text-2xl font-bold text-gray-900">{counts[color]}</div>
          <div className="mt-1 text-xs text-gray-400">
            {((counts[color] / total) * 100).toFixed(0)}%
          </div>
          <div className={`mt-2 h-1 rounded-full ${COLOR_BG_CLASS[color]}`} />
        </div>
      ))}
    </div>
  );
}
