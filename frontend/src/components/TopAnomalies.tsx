import { useNavigate } from "react-router-dom";
import type { AnomalyLogEntry } from "../api/types";
import { AnomalyBadge } from "./AnomalyBadge";

export function TopAnomalies({
  uploadId,
  anomalies,
}: {
  uploadId: string;
  anomalies: AnomalyLogEntry[];
}) {
  const navigate = useNavigate();

  if (anomalies.length === 0) {
    return <p className="text-sm text-gray-500">No anomalies detected — all FCs are clean.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50 text-left text-xs font-semibold text-gray-500 uppercase">
          <tr>
            <th className="px-3 py-2">FC</th>
            <th className="px-3 py-2">Date</th>
            <th className="px-3 py-2">Issue</th>
            <th className="px-3 py-2">Severity</th>
          </tr>
        </thead>
        <tbody>
          {anomalies.map((a, i) => (
            <tr
              key={`${a.fc_name}-${a.date}-${a.line_item}-${i}`}
              onClick={() => navigate(`/dashboard/${uploadId}/fc/${encodeURIComponent(a.fc_name)}`)}
              className="cursor-pointer border-t border-gray-100 hover:bg-gray-50"
            >
              <td className="px-3 py-2 font-medium text-gray-800">{a.fc_name}</td>
              <td className="px-3 py-2 text-gray-500">{a.date}</td>
              <td className="px-3 py-2 text-gray-700">
                {a.line_item}: {a.actual_pct}% (target {a.target_range})
              </td>
              <td className="px-3 py-2">
                <AnomalyBadge severity={a.severity} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
