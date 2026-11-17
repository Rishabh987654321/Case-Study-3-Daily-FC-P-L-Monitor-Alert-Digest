import { apiClient } from "./client";
import type {
  AnomalyLogEntry,
  ConfigResponse,
  DashboardData,
  DigestResponse,
  FCDayDetail,
  PaginatedResponse,
  UploadCreateResponse,
  UploadSummary,
} from "./types";

export async function uploadFile(file: File, name?: string): Promise<UploadCreateResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (name) formData.append("name", name);
  const res = await apiClient.post<UploadCreateResponse>("/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function getUpload(id: string): Promise<UploadSummary> {
  const res = await apiClient.get<UploadSummary>(`/upload/${id}`);
  return res.data;
}

export async function listUploads(
  page = 1,
  pageSize = 20,
): Promise<PaginatedResponse<UploadSummary>> {
  const res = await apiClient.get<PaginatedResponse<UploadSummary>>("/uploads", {
    params: { page, page_size: pageSize },
  });
  return res.data;
}

export async function deleteUpload(id: string): Promise<void> {
  await apiClient.delete(`/upload/${id}`);
}

export async function getDashboard(id: string): Promise<DashboardData> {
  const res = await apiClient.get<DashboardData>(`/upload/${id}/dashboard`);
  return res.data;
}

export interface PnLQueryParams {
  fc?: string;
  date_from?: string;
  date_to?: string;
  color?: string;
  page?: number;
  page_size?: number;
}

export async function getPnLData(
  id: string,
  params: PnLQueryParams = {},
): Promise<PaginatedResponse<FCDayDetail>> {
  const res = await apiClient.get<PaginatedResponse<FCDayDetail>>(`/upload/${id}/pnl`, {
    params,
  });
  return res.data;
}

export async function getFCDayDetail(id: string, fcDayId: string): Promise<FCDayDetail> {
  const res = await apiClient.get<FCDayDetail>(`/upload/${id}/pnl/${fcDayId}`);
  return res.data;
}

export interface AnomalyQueryParams {
  fc?: string;
  severity?: string;
  line_item?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export async function getAnomalies(
  id: string,
  params: AnomalyQueryParams = {},
): Promise<PaginatedResponse<AnomalyLogEntry>> {
  const res = await apiClient.get<PaginatedResponse<AnomalyLogEntry>>(
    `/upload/${id}/anomalies`,
    { params },
  );
  return res.data;
}

export interface DigestQueryParams {
  fc?: string;
  date?: string;
  color?: string;
}

export async function getDigests(
  id: string,
  params: DigestQueryParams = {},
): Promise<DigestResponse[]> {
  const res = await apiClient.get<{ digests: DigestResponse[] }>(`/upload/${id}/digests`, {
    params,
  });
  return res.data.digests;
}

export function getExportUrl(id: string): string {
  return `/api/upload/${id}/export`;
}

export function getAnomaliesExportUrl(id: string): string {
  return `/api/upload/${id}/export/anomalies`;
}

export async function getConfig(): Promise<ConfigResponse> {
  const res = await apiClient.get<ConfigResponse>("/config");
  return res.data;
}
