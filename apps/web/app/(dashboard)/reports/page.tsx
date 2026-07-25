"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/auth";
import { EmptyState } from "@/components/EmptyState";

interface DailyReport {
  id: string;
  report_date: string;
  emails_handled: number;
  drafts_pending: number;
  leads_created: number;
  follow_ups_overdue: number;
  tasks_completed: number;
  metrics: Record<string, unknown>;
  narrative: string;
  generated_at: string;
}

interface PaginatedReports {
  items: DailyReport[];
  total: number;
}

export default function ReportsPage() {
  const [reports, setReports] = useState<DailyReport[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const load = useCallback(() => {
    apiFetch<PaginatedReports>("/v1/reports?page_size=30")
      .then((res) => setReports(res.items))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load reports."));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function generateToday() {
    setGenerating(true);
    setError(null);
    try {
      await apiFetch("/v1/reports/generate", { method: "POST", body: JSON.stringify({}) });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate report.");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Reports</h1>
          <p className="mt-1 text-sm text-zinc-500">
            A day-end summary of emails handled, drafts pending, leads created, and tasks completed. Every
            number below is computed directly from stored data before the AI writes a word of narrative on
            top of it.
          </p>
        </div>
        <button
          onClick={generateToday}
          disabled={generating}
          className="shrink-0 rounded bg-zinc-900 dark:bg-zinc-100 text-zinc-50 dark:text-zinc-900 px-3 py-1.5 text-xs font-medium disabled:opacity-60"
        >
          {generating ? "Generating…" : "Generate today's report"}
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {reports === null && !error && <p className="text-sm text-zinc-500">Loading…</p>}

      {reports !== null && reports.length === 0 && (
        <EmptyState
          title="No reports yet"
          description="Generate today's report to see real computed metrics and an AI-written summary."
        />
      )}

      {reports !== null && reports.length > 0 && (
        <div className="flex flex-col gap-4">
          {reports.map((report) => (
            <div key={report.id} className="rounded-lg border border-zinc-200 dark:border-zinc-800 p-4">
              <h2 className="text-sm font-medium">{report.report_date}</h2>
              <div className="mt-2 grid grid-cols-5 gap-2 text-center">
                <Metric label="Emails" value={report.emails_handled} />
                <Metric label="Drafts pending" value={report.drafts_pending} />
                <Metric label="Leads" value={report.leads_created} />
                <Metric label="Overdue" value={report.follow_ups_overdue} />
                <Metric label="Done tasks" value={report.tasks_completed} />
              </div>
              <p className="mt-3 text-sm text-zinc-700 dark:text-zinc-300 whitespace-pre-wrap">
                {report.narrative}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-zinc-200 dark:border-zinc-800 py-2">
      <div className="text-lg font-semibold">{value}</div>
      <div className="text-xs text-zinc-500">{label}</div>
    </div>
  );
}
