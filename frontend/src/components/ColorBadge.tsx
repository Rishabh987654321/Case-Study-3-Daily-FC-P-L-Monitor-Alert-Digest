import type { ColorCode } from "../api/types";
import { COLOR_BG_CLASS, COLOR_LABEL } from "../lib/colors";

interface ColorBadgeProps {
  color: ColorCode;
  size?: "sm" | "md";
}

export function ColorBadge({ color, size = "md" }: ColorBadgeProps) {
  const dotSize = size === "sm" ? "w-2 h-2" : "w-2.5 h-2.5";
  return (
    <span className="inline-flex items-center gap-1.5 text-sm font-medium text-gray-700">
      <span className={`inline-block rounded-full ${dotSize} ${COLOR_BG_CLASS[color]}`} />
      {COLOR_LABEL[color]}
    </span>
  );
}
