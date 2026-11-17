import axios from "axios";
import type { ApiErrorBody } from "./types";

export const apiClient = axios.create({
  baseURL: "/api",
});

/** Extracts a human-readable message from our standard {error:{code,message}} shape. */
export function getApiErrorMessage(err: unknown): string {
  if (axios.isAxiosError<ApiErrorBody>(err)) {
    if (err.response?.data?.error?.message) {
      return err.response.data.error.message;
    }
    if (err.code === "ERR_NETWORK" || !err.response) {
      return "Server unreachable. Check that the backend is running.";
    }
    return err.message;
  }
  return err instanceof Error ? err.message : "Unknown error";
}
