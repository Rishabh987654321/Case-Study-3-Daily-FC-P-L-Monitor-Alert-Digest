import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getApiErrorMessage } from "../api/client";
import { deleteUpload, listUploads } from "../api/upload";
import { useToast } from "../lib/toast";

const STATUS_CLASS: Record<string, string> = {
  processing: "bg-amber-100 text-amber-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

export function HistoryPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showError, showInfo } = useToast();

  const query = useQuery({
    queryKey: ["uploads"],
    queryFn: () => listUploads(1, 50),
  });

  async function handleDelete(e: React.MouseEvent, id: string) {
    e.stopPropagation();
    if (!window.confirm("Delete this upload and all associated data? This cannot be undone.")) {
      return;
    }
    try {
      await deleteUpload(id);
      await queryClient.invalidateQueries({ queryKey: ["uploads"] });
      showInfo("Upload deleted.");
    } catch (err) {
      showError(getApiErrorMessage(err));
    }
  }

  if (query.isLoading) return <p className="text-gray-500">Loading…</p>;
  if (query.isError) return <p className="text-red-600">{getApiErrorMessage(query.error)}</p>;

  const uploads = query.data?.items ?? [];

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Upload History</h1>

      {uploads.length === 0 ? (
        <p className="text-gray-500">No uploads yet. Go to Upload to analyze your first file.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs font-semibold text-gray-500 uppercase">
              <tr>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Filename</th>
                <th className="px-3 py-2">Date</th>
                <th className="px-3 py-2">FCs</th>
                <th className="px-3 py-2">Days</th>
                <th className="px-3 py-2">Anomalies</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {uploads.map((u) => (
                <tr
                  key={u.id}
                  onClick={() => navigate(`/dashboard/${u.id}`)}
                  className="cursor-pointer border-t border-gray-100 hover:bg-gray-50"
                >
                  <td className="px-3 py-2 font-medium text-gray-800">{u.name || "—"}</td>
                  <td className="px-3 py-2 text-gray-600">{u.filename}</td>
                  <td className="px-3 py-2 text-gray-500">
                    {new Date(u.created_at).toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-gray-600">{u.fc_count}</td>
                  <td className="px-3 py-2 text-gray-600">{u.day_count}</td>
                  <td className="px-3 py-2 text-gray-600">{u.anomaly_count}</td>
                  <td className="px-3 py-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${STATUS_CLASS[u.status] ?? ""}`}
                    >
                      {u.status}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      onClick={(e) => handleDelete(e, u.id)}
                      className="text-red-600 hover:underline"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
