"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/auth";
import { EmptyState } from "@/components/EmptyState";

interface AuditLogEntry {
  id: string;
  actor_type: "user" | "ai_employee" | "system";
  action: string;
  resource_type: string;
  created_at: string;
}

export default function ActivityLogPage() {
  const [logs, setLogs] = useState<AuditLogEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<AuditLogEntry[]>("/v1/audit-logs")
      .then(setLogs)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load activity log."));
  }, []);

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold">Activity Log</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Every sensitive action — logins, approval decisions, connected integrations — is recorded here,
          append-only (docs/SECURITY_MODEL.md §7). Nothing is ever edited or deleted from this list.
        </p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {logs === null && !error && <p className="text-sm text-zinc-500">Loading…</p>}

      {logs !== null && logs.length === 0 && (
        <EmptyState
          title="No activity yet"
          description="Actions you and your AI employee take — approving a draft, connecting an integration — will show up here as they happen."
        />
      )}

      {logs !== null && logs.length > 0 && (
        <table className="text-sm w-full border-collapse">
          <thead>
            <tr className="text-left text-zinc-500 border-b border-zinc-200 dark:border-zinc-800">
              <th className="py-2 pr-4 font-medium">When</th>
              <th className="py-2 pr-4 font-medium">Actor</th>
              <th className="py-2 pr-4 font-medium">Action</th>
              <th className="py-2 font-medium">Resource</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id} className="border-b border-zinc-100 dark:border-zinc-900">
                <td className="py-2 pr-4 text-zinc-500">{new Date(log.created_at).toLocaleString()}</td>
                <td className="py-2 pr-4">{log.actor_type}</td>
                <td className="py-2 pr-4">{log.action}</td>
                <td className="py-2 text-zinc-500">{log.resource_type}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
