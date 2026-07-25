"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL } from "@/lib/config";

type ProbeStatus = "checking" | "ok" | "down";

function useProbe(path: string): ProbeStatus {
  const [status, setStatus] = useState<ProbeStatus>("checking");

  useEffect(() => {
    let cancelled = false;

    fetch(`${API_BASE_URL}${path}`)
      .then((res) => {
        if (!cancelled) setStatus(res.ok ? "ok" : "down");
      })
      .catch(() => {
        if (!cancelled) setStatus("down");
      });

    return () => {
      cancelled = true;
    };
  }, [path]);

  return status;
}

function StatusBadge({ label, status }: { label: string; status: ProbeStatus }) {
  const color =
    status === "ok" ? "bg-green-500" : status === "down" ? "bg-red-500" : "bg-zinc-400 animate-pulse";

  return (
    <div className="flex items-center gap-2 rounded-lg border border-zinc-200 dark:border-zinc-800 px-4 py-3">
      <span className={`h-2.5 w-2.5 rounded-full ${color}`} />
      <span className="font-medium">{label}</span>
      <span className="text-sm text-zinc-500">{status}</span>
    </div>
  );
}

export function ApiStatusProbes() {
  const liveness = useProbe("/healthz");
  const readiness = useProbe("/readyz");

  return (
    <div className="flex flex-col gap-3">
      <StatusBadge label="API liveness (/healthz)" status={liveness} />
      <StatusBadge label="API readiness (/readyz, DB-backed)" status={readiness} />
    </div>
  );
}
