import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getApiErrorMessage } from "../api/client";
import type { ColorCode } from "../api/types";
import { deleteUpload, getAnomalies, getDashboard, getExportUrl, getUpload } from "../api/upload";
import { ColorGrid } from "../components/ColorGrid";
import { SummaryCards } from "../components/SummaryCards";
import { TopAnomalies } from "../components/TopAnomalies";
import { COLOR_LABEL } from "../lib/colors";
import { useToast } from "../lib/toast";

const ALL_COLORS: ColorCode[] = ["RED", "YELLOW", "GREEN", "BLUE"];
const SEVERITY_RANK: Record<string, number> = { HIGH: 0, MEDIUM: 1, INFO: 2 };

export function DashboardPage() {
  const { id } = useParams<{ id: string }>();
  const uploadId = id!;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showError, showInfo } = useToast();

  const [fcFilter, setFcFilter] = useState<Set<string> | null>(null); // null = all
  const [colorFilter, setColorFilter] = useState<Set<ColorCode>>(new Set(ALL_COLORS));

  const uploadQuery = useQuery({
    queryKey: ["upload", uploadId],
    queryFn: () => getUpload(uploadId),
    refetchInterval: (query) => (query.state.data?.status === "processing" ? 2000 : false),
  });

  const status = uploadQuery.data?.status;

  const dashboardQuery = useQuery({
    queryKey: ["dashboard", uploadId],
    queryFn: () => getDashboard(uploadId),
    enabled: status === "completed",
  });

  const anomaliesQuery = useQuery({
    queryKey: ["anomalies-all", uploadId],
    queryFn: () => getAnomalies(uploadId, { page_size: 500 }),
    enabled: status === "completed",
  });

  const topAnomalies = useMemo(() => {
    const items = anomaliesQuery.data?.items ?? [];
    return [...items]
      .sort((a, b) => {
        const rankDiff = (SEVERITY_RANK[a.severity] ?? 9) - (SEVERITY_RANK[b.severity] ?? 9);
        if (rankDiff !== 0) return rankDiff;
        return Math.abs(b.deviation) - Math.abs(a.deviation);
      })
      .slice(0, 5);
  }, [anomaliesQuery.data]);

  async function handleDelete() {
    if (!window.confirm("Delete this upload and all associated data? This cannot be undone.")) {
      return;
    }
    try {
      await deleteUpload(uploadId);
      queryClient.removeQueries({ queryKey: ["upload", uploadId] });
      showInfo("Upload deleted.");
      navigate("/history");
    } catch (err) {
      showError(getApiErrorMessage(err));
    }
  }

  function toggleColor(color: ColorCode) {
    setColorFilter((prev) => {
      const next = new Set(prev);
      if (next.has(color)) next.delete(color);
      else next.add(color);
      return next;
    });
  }

  function toggleFc(fc: string, allFcs: string[]) {
    setFcFilter((prev) => {
      const current = prev ?? new Set(allFcs);
      const next = new Set(current);
      if (next.has(fc)) next.delete(fc);
      else next.add(fc);
      return next;
    });
  }

  if (uploadQuery.isLoading) {
    return <p className="text-gray-500">Loading upload…</p>;
  }
  if (uploadQuery.isError) {
    return (
      <p className="text-red-600">{getApiErrorMessage(uploadQuery.error)}</p>
    );
  }

  const upload = uploadQuery.data!;

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {upload.name || upload.filename}
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Analyzed: {upload.fc_count} FCs × {upload.day_count} days
            {upload.anomaly_count > 0 && ` · ${upload.anomaly_count} anomalies`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={upload.status} />
          {upload.status === "completed" && (
            <a
              href={getExportUrl(uploadId)}
              className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Download Report
            </a>
          )}
          <button
            type="button"
            onClick={handleDelete}
            className="rounded-md border border-red-200 bg-white px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50"
          >
            Delete
          </button>
        </div>
      </div>

      {upload.status === "processing" && (
        <div className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-8">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-300 border-t-indigo-600" />
          <p className="text-gray-600">Analyzing data…</p>
        </div>
      )}

      {upload.status === "failed" && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-red-700">
          <p className="font-semibold">Processing failed</p>
          <p className="mt-1 text-sm">{upload.error_message}</p>
        </div>
      )}

      {upload.status === "completed" && dashboardQuery.data && (
        <div className="space-y-8">
          <section>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-gray-900">Daily Status Grid</h2>
              <div className="flex flex-wrap items-center gap-4 text-sm">
                <div className="flex items-center gap-2">
                  {ALL_COLORS.map((c) => (
                    <label key={c} className="flex items-center gap-1 text-gray-600">
                      <input
                        type="checkbox"
                        checked={colorFilter.has(c)}
                        onChange={() => toggleColor(c)}
                      />
                      {COLOR_LABEL[c]}
                    </label>
                  ))}
                </div>
                <div className="flex items-center gap-2 border-l border-gray-200 pl-4">
                  {dashboardQuery.data.fcs.map((fc) => (
                    <label key={fc} className="flex items-center gap-1 text-gray-600">
                      <input
                        type="checkbox"
                        checked={fcFilter ? fcFilter.has(fc) : true}
                        onChange={() => toggleFc(fc, dashboardQuery.data!.fcs)}
                      />
                      {fc}
                    </label>
                  ))}
                </div>
              </div>
            </div>
            <ColorGrid
              uploadId={uploadId}
              data={dashboardQuery.data}
              visibleFcs={dashboardQuery.data.fcs.filter((fc) => (fcFilter ? fcFilter.has(fc) : true))}
              visibleColors={colorFilter}
            />
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-gray-900">Summary</h2>
            <SummaryCards data={dashboardQuery.data} />
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-gray-900">Top 5 Most Critical</h2>
            <TopAnomalies uploadId={uploadId} anomalies={topAnomalies} />
          </section>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    processing: "bg-amber-100 text-amber-700",
    completed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
  };
  return (
    <span className={`rounded-full px-3 py-1 text-xs font-semibold capitalize ${styles[status] ?? ""}`}>
      {status}
    </span>
  );
}
