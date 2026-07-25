"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/auth";
import { EmptyState } from "@/components/EmptyState";

interface Classification {
  category: string;
  priority: string;
  urgency: string;
  sentiment: string;
  requires_reply: boolean;
  contains_lead: boolean;
  contains_task: boolean;
  possible_spam: boolean;
  possible_prompt_injection: boolean;
  confidence: number;
  short_summary: string;
}

interface EmailMessageResponse {
  id: string;
  thread_id: string;
  sender: string;
  recipients: string[];
  subject: string;
  received_at: string;
  classification: Classification | null;
}

interface EmailDetail extends EmailMessageResponse {
  body_text: string;
  leads: { id: string; requested_service: string | null; budget: string | null; deadline: string | null }[];
  tasks: { id: string; title: string; priority: string; status: string }[];
}

interface PaginatedEmails {
  items: EmailMessageResponse[];
  total: number;
}

const PRIORITY_STYLES: Record<string, string> = {
  critical: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  high: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  normal: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  low: "bg-zinc-100 text-zinc-500 dark:bg-zinc-900 dark:text-zinc-500",
};

export default function InboxPage() {
  const [emails, setEmails] = useState<EmailMessageResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<EmailDetail | null>(null);

  const load = useCallback(() => {
    apiFetch<PaginatedEmails>("/v1/emails?page_size=50")
      .then((res) => setEmails(res.items))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load inbox."));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function ingestAndProcess() {
    setBusy(true);
    setError(null);
    try {
      await apiFetch("/v1/emails/ingest-mock", { method: "POST" });
      const res = await apiFetch<PaginatedEmails>("/v1/emails?page_size=50");
      setEmails(res.items);
      await Promise.all(
        res.items
          .filter((m) => m.classification === null)
          .map((m) => apiFetch(`/v1/emails/${m.id}/process`, { method: "POST" }).catch(() => undefined)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to ingest mock inbox.");
    } finally {
      setBusy(false);
    }
  }

  async function openEmail(id: string) {
    try {
      const detail = await apiFetch<EmailDetail>(`/v1/emails/${id}`);
      setSelected(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load email.");
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Inbox</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Mock inbox for local development — no real Gmail/Outlook is connected yet. Every email here is a
            fixed fictional scenario, classified by the real model.
          </p>
        </div>
        <button
          onClick={ingestAndProcess}
          disabled={busy}
          className="shrink-0 rounded bg-zinc-900 dark:bg-zinc-100 text-zinc-50 dark:text-zinc-900 px-3 py-1.5 text-xs font-medium disabled:opacity-60"
        >
          {busy ? "Processing…" : "Ingest + classify mock inbox"}
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {emails === null && !error && <p className="text-sm text-zinc-500">Loading…</p>}

      {emails !== null && emails.length === 0 && (
        <EmptyState
          title="Inbox is empty"
          description="Click 'Ingest + classify mock inbox' to load the 12 fixed mock scenarios and run them through classification."
        />
      )}

      <div className="flex gap-6">
        {emails !== null && emails.length > 0 && (
          <ul className="flex-1 flex flex-col gap-2">
            {emails.map((email) => (
              <li key={email.id}>
                <button
                  onClick={() => openEmail(email.id)}
                  className="w-full text-left rounded-lg border border-zinc-200 dark:border-zinc-800 p-3 hover:bg-zinc-100/60 dark:hover:bg-zinc-900/60"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium truncate">{email.subject}</span>
                    {email.classification && (
                      <span
                        className={`shrink-0 text-xs rounded px-2 py-0.5 ${PRIORITY_STYLES[email.classification.priority]}`}
                      >
                        {email.classification.category}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-zinc-500 truncate mt-1">{email.sender}</p>
                  {email.classification?.possible_prompt_injection && (
                    <p className="text-xs text-red-600 mt-1">⚠ possible prompt injection detected</p>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}

        {selected && (
          <div className="w-96 shrink-0 rounded-lg border border-zinc-200 dark:border-zinc-800 p-4 text-sm">
            <h2 className="font-medium">{selected.subject}</h2>
            <p className="text-xs text-zinc-500 mt-1">From: {selected.sender}</p>
            <p className="mt-3 whitespace-pre-wrap text-zinc-700 dark:text-zinc-300">{selected.body_text}</p>

            {selected.classification && (
              <div className="mt-4 border-t border-zinc-200 dark:border-zinc-800 pt-3">
                <p className="text-xs text-zinc-500">{selected.classification.short_summary}</p>
                <p className="text-xs text-zinc-500 mt-1">
                  confidence {selected.classification.confidence.toFixed(2)} · sentiment{" "}
                  {selected.classification.sentiment}
                </p>
              </div>
            )}

            {selected.leads.length > 0 && (
              <div className="mt-4 border-t border-zinc-200 dark:border-zinc-800 pt-3">
                <p className="text-xs font-medium mb-1">Extracted lead</p>
                {selected.leads.map((lead) => (
                  <p key={lead.id} className="text-xs text-zinc-500">
                    {lead.requested_service ?? "Unspecified service"}
                    {lead.budget ? ` · budget ${lead.budget}` : ""}
                    {lead.deadline ? ` · deadline ${lead.deadline}` : ""}
                  </p>
                ))}
              </div>
            )}

            {selected.tasks.length > 0 && (
              <div className="mt-4 border-t border-zinc-200 dark:border-zinc-800 pt-3">
                <p className="text-xs font-medium mb-1">Extracted tasks</p>
                {selected.tasks.map((task) => (
                  <p key={task.id} className="text-xs text-zinc-500">
                    {task.title} ({task.priority})
                  </p>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
