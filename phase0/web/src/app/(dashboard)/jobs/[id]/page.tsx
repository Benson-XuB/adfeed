"use client";

import { useParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { getJob, getJobResults, processJob, JobDetail, JobResults } from "@/lib/api";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [results, setResults] = useState<JobResults | null>(null);
  const [error, setError] = useState("");

  const fetch = useCallback(async () => {
    if (!token) return;
    try {
      const j = await getJob(id, token);
      setJob(j);
      // 处理中自动轮询
      if (j.status === "processing") {
        setTimeout(fetch, 3000);
      }
      // 完成后加载结果
      if (j.status === "completed") {
        const r = await getJobResults(id, token);
        setResults(r);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Not found");
    }
  }, [id, token]);

  useEffect(() => { fetch(); }, [fetch]);

  const handleProcess = async () => {
    if (!token) return;
    try {
      await processJob(id, token);
      fetch(); // 刷新状态
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  };

  if (error) {
    return (
      <div className="text-center py-20">
        <p className="text-red-600 mb-4">{error}</p>
        <Link href="/dashboard" className="btn btn-sm">Back</Link>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-6 h-6 border-2 border-stone-800 border-t-transparent animate-spin" />
      </div>
    );
  }

  const statusTag = (s: string) => {
    if (s === "completed") return <span className="tag tag-success">Completed</span>;
    if (s === "processing") return <span className="tag tag-warn">Processing</span>;
    if (s === "failed") return <span className="tag tag-danger">Failed</span>;
    return <span className="tag">{s}</span>;
  };

  return (
    <div>
      <Link href="/dashboard" className="text-xs text-stone-400 hover:text-stone-700 mb-4 inline-block">
        ← Back to overview
      </Link>

      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-black tracking-tight">{job.filename}</h1>
          <p className="text-sm text-stone-400 mt-1">
            Uploaded {new Date(job.created_at).toLocaleString()}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {statusTag(job.status)}
          {job.status === "uploaded" && (
            <button onClick={handleProcess} className="btn btn-accent btn-sm">
              Start processing
            </button>
          )}
          {job.status === "failed" && (
            <button onClick={handleProcess} className="btn btn-sm">
              Retry
            </button>
          )}
        </div>
      </div>

      {/* Quota truncation notice */}
      {job.truncated && job.status === "completed" && (
        <div className="mb-6 p-4 border border-amber-200 bg-amber-50 text-amber-800 text-sm rounded">
          <strong>Quota limit applied</strong> — Only {job.done_rows} of {job.total_rows} rows were
          processed due to your plan limit.{" "}
          <Link href="/upgrade" className="underline font-bold text-amber-900">
            Upgrade your plan →
          </Link>{" "}
          to process all rows in future uploads.
        </div>
      )}

      {/* Stats grid */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {[
          ["Total rows", String(job.total_rows)],
          ["OK", String(job.ok_rows)],
          ["Failed", String(job.fail_rows)],
          ["Progress", `${job.progress_pct}%`],
        ].map(([label, value]) => (
          <div key={label} className="card">
            <div className="text-xs text-stone-400 tracking-widest uppercase mb-1">{label}</div>
            <div className="text-xl font-black">{value}</div>
          </div>
        ))}
      </div>

      {/* Progress bar */}
      {job.status === "processing" && (
        <div className="card mb-8">
          <div className="text-xs text-stone-400 mb-2">Processing {job.done_rows} of {job.total_rows} rows...</div>
          <div className="progress-bar">
            <div className="progress-bar-fill" style={{ width: `${job.progress_pct}%` }} />
          </div>
        </div>
      )}

      {/* Error */}
      {job.error_msg && (
        <div className="card border-red-200 bg-red-50 mb-8">
          <div className="text-xs text-stone-400 tracking-widest uppercase mb-1">Error</div>
          <div className="text-sm text-red-700">{job.error_msg}</div>
        </div>
      )}

      {/* Results table */}
      {job.status === "completed" && results && results.rows.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-3">
            <div className="text-xs text-stone-400 tracking-widest uppercase">
              Results {results.total ? `(${results.total} items)` : ""}
            </div>
            <Link href="/feeds" className="btn btn-sm">
              Download feeds →
            </Link>
          </div>
          <div className="card overflow-x-auto p-0">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-stone-100 bg-stone-50">
                  {Object.keys(results.rows[0] || {}).filter(k => !k.startsWith("_")).slice(0, 6).map((col) => (
                    <th key={col} className="px-3 py-2 text-left font-bold text-stone-400 whitespace-nowrap">
                      {col.length > 20 ? col.slice(0, 20) + "…" : col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {results.rows.map((row, i) => (
                  <tr key={i} className="border-b border-stone-50 hover:bg-stone-50/50">
                    {Object.keys(row).filter(k => !k.startsWith("_")).slice(0, 6).map((col) => (
                      <td key={col} className="px-3 py-2 text-stone-700 max-w-[200px] truncate" title={row[col]}>
                        {row[col]}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {results.rows.length >= 20 && (
              <div className="px-4 py-2 text-xs text-stone-400 border-t border-stone-50">
                Showing first {results.rows.length} results.{" "}
                <Link href="/feeds" className="underline">Download full data →</Link>
              </div>
            )}
          </div>
        </div>
      )}

      {job.status === "completed" && (!results || results.rows.length === 0) && (
        <div className="card">
          <div className="text-xs text-stone-400 tracking-widest uppercase mb-3">Next step</div>
          <p className="text-sm text-stone-600 mb-4">
            Your feed XMLs are ready. Download them from the Feeds page.
          </p>
          <Link href="/feeds" className="btn btn-sm">
            Go to feeds →
          </Link>
        </div>
      )}
    </div>
  );
}
