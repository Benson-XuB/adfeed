"use client";

import { useAuth } from "@/lib/auth";
import { listJobs, JobSummary } from "@/lib/api";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";

export default function DashboardPage() {
  const { user, token } = useAuth();
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchJobs = useCallback(async () => {
    if (!token) return;
    try {
      const j = await listJobs(token);
      setJobs(j);
    } catch { /* ignore */ }
    setLoading(false);
  }, [token]);

  useEffect(() => { fetchJobs(); }, [fetchJobs]);

  const statusTag = (s: string) => {
    if (s === "completed") return <span className="tag tag-success">Done</span>;
    if (s === "processing") return <span className="tag tag-warn">Processing</span>;
    if (s === "failed") return <span className="tag tag-danger">Failed</span>;
    return <span className="tag">{s}</span>;
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-black tracking-tight">Overview</h1>
          <p className="text-sm text-stone-500 mt-1">
            {user?.quota_remaining} of {user?.quota_total} SKUs remaining this month
          </p>
        </div>
        <Link href="/upload" className="btn btn-sm">
          ↑ New upload
        </Link>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        {[
          ["Total jobs", String(jobs.length)],
          ["Completed", String(jobs.filter((j) => j.status === "completed").length)],
          ["SKUs processed", String(jobs.reduce((sum, j) => sum + j.ok_rows, 0))],
        ].map(([label, value]) => (
          <div key={label} className="card">
            <div className="text-xs text-stone-400 tracking-widest uppercase mb-1">{label}</div>
            <div className="text-2xl font-black">{value}</div>
          </div>
        ))}
      </div>

      {/* Recent jobs */}
      <h2 className="text-sm font-bold tracking-widest uppercase text-stone-400 mb-4">Recent Uploads</h2>
      {loading ? (
        <div className="text-sm text-stone-400">Loading...</div>
      ) : jobs.length === 0 ? (
        <div className="card text-center text-sm text-stone-400 py-12">
          No uploads yet.{" "}
          <Link href="/upload" className="underline text-stone-700">Upload your first file.</Link>
        </div>
      ) : (
        <div className="space-y-2">
          {jobs.map((j) => (
            <Link
              key={j.id}
              href={`/jobs/${j.id}`}
              className="card flex items-center justify-between hover:border-stone-400 transition-colors cursor-pointer block"
            >
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{j.filename}</div>
                <div className="text-xs text-stone-400 mt-0.5">
                  {j.ok_rows}/{j.total_rows} rows · {new Date(j.created_at).toLocaleDateString()}
                </div>
              </div>
              <div className="flex items-center gap-4 shrink-0 ml-4">
                {j.status === "uploaded" || j.status === "processing" ? (
                  <div className="w-24">
                    <div className="text-[10px] text-stone-400 text-right mb-1">{j.progress_pct}%</div>
                    <div className="progress-bar">
                      <div className="progress-bar-fill" style={{ width: `${j.progress_pct}%` }} />
                    </div>
                  </div>
                ) : null}
                {statusTag(j.status)}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
