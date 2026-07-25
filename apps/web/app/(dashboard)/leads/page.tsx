"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/auth";
import { EmptyState } from "@/components/EmptyState";

interface Contact {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  company: string | null;
}

interface Lead {
  id: string;
  contact: Contact;
  status: "new" | "contacted" | "awaiting_reply" | "stale" | "won" | "lost";
  requested_service: string | null;
  budget: string | null;
  deadline: string | null;
  confidence: number | null;
  created_at: string;
}

interface PaginatedLeads {
  items: Lead[];
  total: number;
}

const STATUS_OPTIONS: Lead["status"][] = ["new", "contacted", "awaiting_reply", "stale", "won", "lost"];

const STATUS_STYLES: Record<string, string> = {
  new: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  contacted: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  awaiting_reply: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  stale: "bg-zinc-200 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-500",
  won: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  lost: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    apiFetch<PaginatedLeads>("/v1/leads?page_size=100")
      .then((res) => setLeads(res.items))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load leads."));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function updateStatus(id: string, status: Lead["status"]) {
    try {
      await apiFetch(`/v1/leads/${id}/status`, { method: "POST", body: JSON.stringify({ status }) });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update lead status.");
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold">Leads</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Contacts and sales leads the Assistant detects from email. Budget and deadline are only ever shown
          if the email actually stated them — never guessed.
        </p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {leads === null && !error && <p className="text-sm text-zinc-500">Loading…</p>}

      {leads !== null && leads.length === 0 && (
        <EmptyState
          title="No leads yet"
          description="Leads the Assistant extracts from sales-enquiry emails will appear here. Try ingesting the mock inbox from the Inbox page."
        />
      )}

      {leads !== null && leads.length > 0 && (
        <div className="flex flex-col gap-3">
          {leads.map((lead) => (
            <div
              key={lead.id}
              className="rounded-lg border border-zinc-200 dark:border-zinc-800 p-4 flex flex-col gap-2"
            >
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-medium text-sm">{lead.contact.name}</span>
                  <span className="text-xs text-zinc-500 ml-2">{lead.contact.email}</span>
                </div>
                <select
                  value={lead.status}
                  onChange={(e) => updateStatus(lead.id, e.target.value as Lead["status"])}
                  className={`text-xs rounded px-2 py-0.5 border-0 ${STATUS_STYLES[lead.status]}`}
                >
                  {STATUS_OPTIONS.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>
              <p className="text-sm text-zinc-700 dark:text-zinc-300">
                {lead.requested_service ?? "Unspecified service"}
              </p>
              <p className="text-xs text-zinc-500">
                {lead.budget ? `Budget: ${lead.budget}` : "Budget: not stated"}
                {" · "}
                {lead.deadline ? `Deadline: ${lead.deadline}` : "Deadline: not stated"}
                {lead.confidence !== null && ` · confidence ${lead.confidence.toFixed(2)}`}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
