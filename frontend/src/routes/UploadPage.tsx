import { useMutation, useQuery } from "@tanstack/react-query";
import { useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { getApiErrorMessage } from "../api/client";
import { getConfig, uploadFile } from "../api/upload";
import { useToast } from "../lib/toast";

const ALLOWED_EXTENSIONS = [".csv", ".xlsx", ".xls"];

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function validateExtension(file: File): string | null {
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    return `Unsupported file type "${ext || "(none)"}". Use .csv, .xlsx, or .xls.`;
  }
  return null;
}

export function UploadPage() {
  const navigate = useNavigate();
  const { showError } = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: config } = useQuery({ queryKey: ["config"], queryFn: getConfig });
  const maxBytes = (config?.max_file_mb ?? 50) * 1024 * 1024;

  const mutation = useMutation({
    mutationFn: () => uploadFile(file!, name || undefined),
    onSuccess: (res) => {
      navigate(`/dashboard/${res.upload_id}`);
    },
    onError: (err) => {
      showError(getApiErrorMessage(err));
    },
  });

  function pickFile(candidate: File) {
    const extError = validateExtension(candidate);
    if (extError) {
      setFileError(extError);
      setFile(null);
      return;
    }
    if (candidate.size > maxBytes) {
      setFileError(`File exceeds max size of ${config?.max_file_mb ?? 50}MB.`);
      setFile(null);
      return;
    }
    setFileError(null);
    setFile(candidate);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) pickFile(dropped);
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Upload FC Daily Data</h1>

      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`cursor-pointer rounded-lg border-2 border-dashed p-10 text-center transition-colors ${
          dragOver ? "border-indigo-500 bg-indigo-50" : "border-gray-300 bg-white"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ALLOWED_EXTENSIONS.join(",")}
          className="hidden"
          onChange={(e) => {
            const selected = e.target.files?.[0];
            if (selected) pickFile(selected);
          }}
        />
        {file ? (
          <div>
            <div className="mb-1 text-3xl">✅</div>
            <p className="font-medium text-gray-900">{file.name}</p>
            <p className="text-sm text-gray-500">{formatBytes(file.size)}</p>
            <p className="mt-2 text-xs text-gray-400">Click or drop a new file to replace it</p>
          </div>
        ) : (
          <div>
            <div className="mb-2 text-3xl text-gray-400">📄</div>
            <p className="font-medium text-gray-700">
              Drop your FC daily data file here (CSV or Excel)
            </p>
            <p className="mt-1 text-sm text-gray-400">
              Accepts .csv, .xlsx, .xls — up to {config?.max_file_mb ?? 50}MB
            </p>
          </div>
        )}
      </div>

      {fileError && <p className="mt-2 text-sm text-red-600">{fileError}</p>}

      <div className="mt-6">
        <label htmlFor="upload-name" className="mb-1 block text-sm font-medium text-gray-700">
          Upload name (optional)
        </label>
        <input
          id="upload-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g., November Week 1"
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
        />
      </div>

      <button
        type="button"
        disabled={!file || mutation.isPending}
        onClick={() => mutation.mutate()}
        className="mt-6 w-full rounded-md bg-indigo-600 px-4 py-2.5 font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-gray-300"
      >
        {mutation.isPending ? "Uploading…" : "Analyze Data"}
      </button>

      {mutation.isError && (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <p>{getApiErrorMessage(mutation.error)}</p>
          <button
            type="button"
            onClick={() => mutation.mutate()}
            className="mt-2 font-medium underline"
          >
            Retry
          </button>
        </div>
      )}
    </div>
  );
}
