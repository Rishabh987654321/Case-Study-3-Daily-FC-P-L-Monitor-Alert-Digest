import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { getApiErrorMessage } from "../api/client";
import { getAnomalies, getConfig, getPnLData } from "../api/upload";
import { AnomalyLog } from "../components/AnomalyLog";
import { Breadcrumbs } from "../components/Breadcrumbs";
import { CostBreakdownChart } from "../components/CostBreakdownChart";
import { PnLTable } from "../components/PnLTable";
import { TrendChart } from "../components/TrendChart";

export function FCDetailPage() {
  const { id, name } = useParams<{ id: string; name: string }>();
  const uploadId = id!;
  const fcName = decodeURIComponent(name!);

  const configQuery = useQuery({ queryKey: ["config"], queryFn: getConfig });

  const pnlQuery = useQuery({
    queryKey: ["pnl", uploadId, fcName],
    queryFn: () => getPnLData(uploadId, { fc: fcName, page_size: 500 }),
  });

  const anomaliesQuery = useQuery({
    queryKey: ["anomalies", uploadId, fcName],
    queryFn: () => getAnomalies(uploadId, { fc: fcName, page_size: 500 }),
  });

  if (pnlQuery.isLoading) return <p className="text-gray-500">Loading…</p>;
  if (pnlQuery.isError) return <p className="text-red-600">{getApiErrorMessage(pnlQuery.error)}</p>;

  const rows = pnlQuery.data?.items ?? [];
  const sortedRows = [...rows].sort((a, b) => a.date.localeCompare(b.date));

  const avgCm2 = rows.length
    ? (rows.reduce((sum, r) => sum + r.cm2_pct, 0) / rows.length).toFixed(1)
    : "0";
  const colorCounts = rows.reduce<Record<string, number>>((acc, r) => {
    acc[r.color_code] = (acc[r.color_code] ?? 0) + 1;
    return acc;
  }, {});

  const cm2Range = configQuery.data?.cm2 ?? { min: 15, max: 30 };

  return (
    <div>
      <Breadcrumbs
        items={[
          { label: "Dashboard", to: `/dashboard/${uploadId}` },
          { label: fcName },
        ]}
      />

      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{fcName}</h1>
        <p className="mt-1 text-sm text-gray-500">
          {sortedRows[0]?.date} to {sortedRows[sortedRows.length - 1]?.date} · Avg CM2% {avgCm2}% ·{" "}
          {Object.entries(colorCounts)
            .map(([color, count]) => `${color} ${count}`)
            .join(" · ")}
        </p>
      </div>

      <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TrendChart rows={sortedRows} cm2Min={cm2Range.min} cm2Max={cm2Range.max} />
        <CostBreakdownChart rows={sortedRows} />
      </div>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-semibold text-gray-900">Daily P&amp;L</h2>
        <PnLTable rows={sortedRows} />
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold text-gray-900">Anomaly Log</h2>
        <AnomalyLog anomalies={anomaliesQuery.data?.items ?? []} />
      </section>
    </div>
  );
}
