"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { uploadFile, UploadPreview } from "@/lib/api";
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
  const [error, setError] = useState("");
  const [processing, setProcessing] = useState(false);

  const toggleCountry = (code: string) => {
    setSelectedCountries((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  };

  const handleUpload = async () => {
    if (!file || !token) return;
    setUploading(true);
    setError("");
    try {
      const result = await uploadFile(file, selectedCountries, token);
      setPreview(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
    }
    setUploading(false);
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

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-black tracking-tight mb-2">Upload</h1>
      <p className="text-sm text-stone-500 mb-8">
        Drop an Excel, CSV, or text file from any 1688 supplier, ERP, or marketplace.
      </p>

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

      {/* Preview */}
      {preview && (
        <div className="mt-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-bold">{preview.filename}</div>
              <div className="text-xs text-stone-400">
                {preview.total_rows} rows detected · {preview.countries.join(", ")}
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={() => { setFile(null); setPreview(null); }} className="btn btn-outline btn-sm">
                Cancel
              </button>
              <button onClick={handleProcess} disabled={processing} className="btn btn-sm">
                {processing ? "Starting..." : "Process all →"}
              </button>
            </div>
          </div>

          {/* Preview table */}
          {preview.preview_rows.length > 0 && (
            <div className="card overflow-x-auto p-0">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-stone-100 bg-stone-50">
                    {Object.keys(preview.preview_rows[0] || {}).slice(0, 6).map((col) => (
                      <th key={col} className="px-4 py-2 text-left font-bold text-stone-400 tracking-wider uppercase">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.preview_rows.map((row, i) => (
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
              {preview.total_rows > 10 && (
                <div className="px-4 py-2 text-xs text-stone-400">
                  Showing 10 of {preview.total_rows} rows
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
