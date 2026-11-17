import type { ColorCode } from "../api/types";

export const COLOR_HEX: Record<ColorCode, string> = {
  RED: "#EF4444",
  YELLOW: "#F59E0B",
  GREEN: "#22C55E",
  BLUE: "#3B82F6",
};

export const COLOR_BG_CLASS: Record<ColorCode, string> = {
  RED: "bg-red-500",
  YELLOW: "bg-amber-500",
  GREEN: "bg-green-500",
  BLUE: "bg-blue-500",
};

export const COLOR_TEXT_CLASS: Record<ColorCode, string> = {
  RED: "text-red-600",
  YELLOW: "text-amber-600",
  GREEN: "text-green-600",
  BLUE: "text-blue-600",
};

export const COLOR_LABEL: Record<ColorCode, string> = {
  RED: "Red",
  YELLOW: "Yellow",
  GREEN: "Green",
  BLUE: "Blue",
};

export const COLOR_MEANING: Record<ColorCode, string> = {
  RED: "Margin crisis — immediate attention",
  YELLOW: "Warning zone — approaching limits",
  GREEN: "Healthy — within target",
  BLUE: "Suspicious — check for underreported costs",
};

export const SEVERITY_CLASS: Record<string, string> = {
  HIGH: "bg-red-100 text-red-700 border-red-300",
  MEDIUM: "bg-orange-100 text-orange-700 border-orange-300",
  INFO: "bg-gray-100 text-gray-600 border-gray-300",
};
