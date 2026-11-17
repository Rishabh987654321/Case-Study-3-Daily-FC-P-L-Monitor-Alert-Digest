export type ColorCode = "RED" | "YELLOW" | "GREEN" | "BLUE";

export type UploadStatus = "processing" | "completed" | "failed";

export interface UploadCreateResponse {
  upload_id: string;
  status: string;
  filename: string;
}

export interface UploadSummary {
  id: string;
  filename: string;
  name: string | null;
  status: UploadStatus;
  error_message: string | null;
  fc_count: number;
  day_count: number;
  anomaly_count: number;
  created_at: string;
  completed_at: string | null;
}

export interface AnomalyInline {
  line_item: string;
  actual_pct: number;
  target_min: number;
  target_max: number;
  deviation: number;
  status: string;
  severity: "HIGH" | "MEDIUM" | "INFO";
}

export interface FCDaySummary {
  fc_name: string;
  date: string;
  cm2_pct: number;
  color_code: ColorCode;
  anomaly_count: number;
}

export interface FCDayDetail {
  id: string;
  fc_name: string;
  date: string;
  revenue: number;
  manpower_cost: number;
  packaging_cost: number;
  power_fuel: number;
  fc_rent: number;
  equipment_rentals: number;
  overheads: number;
  cm1: number;
  cm1_pct: number;
  cm2: number;
  cm2_pct: number;
  manpower_pct: number;
  packaging_pct: number;
  power_fuel_pct: number;
  fc_rent_pct: number;
  equipment_pct: number;
  overheads_pct: number;
  color_code: ColorCode;
  anomalies: AnomalyInline[];
  insight: string;
}

export interface DashboardData {
  dates: string[];
  fcs: string[];
  grid: Record<string, FCDaySummary[]>;
}

export interface AnomalyLogEntry {
  date: string;
  fc_name: string;
  line_item: string;
  actual_pct: number;
  target_range: string;
  deviation: number;
  status: string;
  severity: "HIGH" | "MEDIUM" | "INFO";
}

export interface DigestResponse {
  fc_name: string;
  date: string;
  color_code: ColorCode;
  summary_text: string;
  html_content: string;
  generation_mode: "llm" | "rule";
}

export interface PaginatedResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface ConfigRangePair {
  min: number;
  max: number;
}

export interface ConfigResponse {
  targets: Record<string, ConfigRangePair>;
  cm1: ConfigRangePair;
  cm2: ConfigRangePair;
  cm_tolerance: number;
  max_file_mb: number;
  notify_channel: string;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
  };
}
