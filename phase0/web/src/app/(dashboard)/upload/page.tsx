"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { uploadFile, UploadPreview, getJob, JobDetail } from "@/lib/api";
import { processJob } from "@/lib/api";

const COUNTRIES = [
  { code: "US", label: "United States" },
  { code: "DE", label: "Germany" },
  { code: "FR", label: "France" },
  { code: "ES", label: "Spain" },
  { code: "IT", label: "Italy" },
];

export default function UploadPage() {
  const { token, user } = useAuth();
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [selectedCountries, setSelectedCountries] = useState<string[]>(["US"]);
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<UploadPreview | null>(null);
  const [jobDetail, setJobDetail] = useState<JobDetail | null>(null);
  const [error, setError] = useState("");
  const [processing, setProcessing] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);

  const toggleCountry = (code: string) => {
    setSelectedCountries((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  };

  const pollUntilAnalyzed = async (jobId: string) => {
    if (!token) return;
    setAnalyzing(true);
    for (let i = 0; i < 60; i++) {
      await new Promise((r) => setTimeout(r, 1000));
      try {
        const j = await getJob(jobId, token);
        if (j.status === "uploaded") {
          setJobDetail(j);
          setAnalyzing(false);
          return;
        }
        if (j.status === "failed") {
          setError(j.error_msg || "File analysis failed");
          setAnalyzing(false);
          return;
        }
      } catch {
        // continue polling
      }
    }
    setError("File analysis timed out. Please try again.");
    setAnalyzing(false);
  };

  const handleUpload = async () => {
    if (!file || !token) return;
    setUploading(true);
    setError("");
    try {
      const result = await uploadFile(file, selectedCountries, token);
      setPreview(result);
      setUploading(false);
      // 开始轮询，等后台分析完成
      pollUntilAnalyzed(result.job_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setUploading(false);
    }
  };

  const handleProcess = async () => {
    if (!preview || !token) return;
    setProcessing(true);
    try {
      await processJob(preview.job_id, token);
      router.push(`/jobs/${preview.job_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Processing failed");
      setProcessing(false);
    }
  };

  // 从 jobDetail 拿到实际的总行数和预览数据
  const totalRows = jobDetail?.total_rows ?? 0;
  const previewRows = jobDetail?.preview_rows ?? [];
  const willTruncate = preview && totalRows > 0 && (preview.quota_remaining < totalRows);
  const processableRows = Math.min(totalRows, preview?.quota_remaining ?? 0);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-black tracking-tight mb-2">Upload</h1>
      <p className="text-sm text-stone-500 mb-4">
        Drop an Excel, CSV, or text file from any 1688 supplier, ERP, or marketplace.
      </p>

      {/* Quota indicator */}
      {user && user.quota_remaining > 0 && (
        <div className="flex items-center gap-2 mb-6 text-xs text-stone-400">
          <span>Quota: {user.quota_used}/{user.quota_total} rows used</span>
          <span className="w-24 h-1.5 bg-stone-100 rounded-full overflow-hidden">
            <span className="block h-full bg-amber-400 rounded-full"
              style={{ width: `${Math.min(100, (user.quota_used / user.quota_total) * 100)}%` }} />
          </span>
        </div>
      )}

      {/* Quota exhausted warning */}
      {user && user.quota_remaining <= 0 && (
        <div className="card border-red-200 bg-red-50 mb-6">
          <div className="font-bold text-red-700 mb-1">Monthly quota exhausted</div>
          <p className="text-sm text-red-600 mb-3">
            You have used {user?.quota_used} of {user?.quota_total} SKUs this month. Upgrade to continue.
          </p>
          <Link href="/upgrade" className="btn btn-sm">
            Upgrade now →
          </Link>
        </div>
      )}

      {/* Country selector */}
      <div className="mb-6">
        <div className="text-xs text-stone-400 tracking-widest uppercase mb-2">Target countries</div>
        <div className="flex flex-wrap gap-2">
          {COUNTRIES.map(({ code, label }) => (
            <button
              key={code}
              onClick={() => toggleCountry(code)}
              className={`px-3 py-1.5 text-xs font-bold border-2 transition-colors ${
                selectedCountries.includes(code)
                  ? "bg-stone-900 text-white border-stone-900"
                  : "border-stone-200 text-stone-500 hover:border-stone-400"
              }`}
            >
              {code} · {label}
            </button>
          ))}
        </div>
      </div>

      {/* Drop zone */}
      {!preview && (
        <div
          onDrop={onDrop}
          onDragOver={(e) => e.preventDefault()}
          className="card border-dashed border-2 py-16 text-center cursor-pointer hover:border-stone-400 transition-colors"
        >
          {file ? (
            <div>
              <div className="text-3xl mb-3">📄</div>
              <div className="font-bold mb-1">{file.name}</div>
              <div className="text-xs text-stone-400">
                {(file.size / 1024).toFixed(1)} KB · {selectedCountries.join(", ")}
              </div>
              <button
                onClick={() => setFile(null)}
                className="text-xs text-stone-400 underline mt-3"
              >
                Choose a different file
              </button>
            </div>
          ) : (
            <div>
              <div className="text-3xl mb-3">↑</div>
              <div className="font-bold mb-1">Drop your file here</div>
              <div className="text-xs text-stone-400">or click to browse</div>
              <input
                type="file"
                accept=".xlsx,.xls,.csv,.txt"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) setFile(f); }}
                className="absolute inset-0 opacity-0 cursor-pointer"
              />
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      {file && !preview && (
        <div className="mt-4">
          <button
            onClick={handleUpload}
            disabled={uploading || selectedCountries.length === 0}
            className="btn w-full justify-center py-3 text-base"
          >
            {uploading ? "Analyzing..." : `Upload & preview`}
          </button>
          {selectedCountries.length === 0 && (
            <p className="text-xs text-red-500 mt-2">Select at least one target country.</p>
          )}
        </div>
      )}

      {error && <div className="mt-4 p-3 border border-red-200 bg-red-50 text-red-700 text-sm">{error}</div>}

      {/* Analyzing spinner */}
      {analyzing && (
        <div className="mt-6 flex items-center gap-3 text-stone-500">
          <div className="w-5 h-5 border-2 border-stone-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Analyzing file...</span>
        </div>
      )}

      {/* Preview (shown after analysis complete) */}
      {preview && jobDetail && jobDetail.status === "uploaded" && (
        <div className="mt-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-bold">{preview.filename}</div>
              <div className="text-xs text-stone-400">
                {totalRows} rows detected · {preview.countries.join(", ")}
              </div>
              {willTruncate && (
                <div className="mt-2 p-3 border border-amber-200 bg-amber-50 text-amber-800 text-sm rounded">
                  <strong>Quota limit</strong> — Your plan has{" "}
                  <strong>{preview.quota_remaining} of {preview.quota_total}</strong> rows remaining
                  this month. Only the <strong>first {processableRows}</strong> of{" "}
                  {totalRows} rows will be processed.{" "}
                  <Link href="/upgrade" className="underline font-bold text-amber-900">
                    Upgrade →
                  </Link> to process all.
                </div>
              )}
            </div>
            <div className="flex gap-2">
              <button onClick={() => { setFile(null); setPreview(null); setJobDetail(null); }} className="btn btn-outline btn-sm">
                Cancel
              </button>
              <button onClick={handleProcess} disabled={processing} className="btn btn-sm">
                {processing ? "Starting..." : willTruncate ? `Process first ${processableRows} →` : "Process all →"}
              </button>
            </div>
          </div>

          {/* Preview table */}
          {previewRows.length > 0 && (
            <div className="card overflow-x-auto p-0">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-stone-100 bg-stone-50">
                    {Object.keys(previewRows[0] || {}).slice(0, 6).map((col) => (
                      <th key={col} className="px-4 py-2 text-left font-bold text-stone-400 tracking-wider uppercase">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {previewRows.map((row, i) => (
                    <tr key={i} className="border-b border-stone-50">
                      {Object.values(row).slice(0, 6).map((val, j) => (
                        <td key={j} className="px-4 py-2 text-stone-600 max-w-[200px] truncate">
                          {String(val).slice(0, 60)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {totalRows > 10 && (
                <div className="px-4 py-2 text-xs text-stone-400">
                  Showing 10 of {totalRows} rows
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
