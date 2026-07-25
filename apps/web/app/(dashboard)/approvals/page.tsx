"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/auth";
import { EmptyState } from "@/components/EmptyState";

interface ApprovalRequest {
  id: string;
  action_type: string;
  payload: Record<string, unknown>;
  resolved_payload: Record<string, unknown> | null;
  simulated_send_result: Record<string, unknown> | null;
  status: "pending" | "approved" | "rejected" | "edited" | "expired" | "cancelled";
  requested_at: string;
  decided_at: string | null;
  decision_reason: string | null;
}

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<ApprovalRequest[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [decidingId, setDecidingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editedBody, setEditedBody] = useState("");

  const load = useCallback(() => {
    apiFetch<ApprovalRequest[]>("/v1/approvals")
      .then(setApprovals)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load approvals."));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function decide(id: string, approve: boolean, editedPayload?: Record<string, unknown>) {
    setDecidingId(id);
    try {
      await apiFetch(`/v1/approvals/${id}/decide`, {
        method: "POST",
        body: JSON.stringify({ approve, edited_payload: editedPayload ?? null }),
      });
      setEditingId(null);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record decision.");
    } finally {
      setDecidingId(null);
    }
  }

  function startEditing(approval: ApprovalRequest) {
    setEditingId(approval.id);
    setEditedBody(typeof approval.payload.body === "string" ? approval.payload.body : "");
  }

  function submitEdit(approval: ApprovalRequest) {
    decide(approval.id, true, { ...approval.payload, body: editedBody });
  }

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold">Approvals</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Every irreversible action the AI Sales &amp; Operations Assistant proposes waits here for a
          human decision before anything executes (docs/SECURITY_MODEL.md §5). Approving a reply calls a
          mock connector only — no real email is ever sent.
        </p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {approvals === null && !error && <p className="text-sm text-zinc-500">Loading…</p>}

      {approvals !== null && approvals.length === 0 && (
        <EmptyState
          title="No approvals yet"
          description="Proposed actions — like a drafted email reply — will appear here for you to approve, edit, or reject."
        />
      )}

      {approvals !== null && approvals.length > 0 && (
        <div className="flex flex-col gap-3">
          {approvals.map((approval) => (
            <div
              key={approval.id}
              className="rounded-lg border border-zinc-200 dark:border-zinc-800 p-4 flex flex-col gap-2"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-sm">{approval.action_type}</span>
                <span
                  className={`text-xs rounded px-2 py-0.5 ${
                    approval.status === "pending"
                      ? "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
                      : approval.status === "approved"
                        ? "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300"
                        : "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300"
                  }`}
                >
                  {approval.status}
                </span>
              </div>

              {editingId === approval.id ? (
                <textarea
                  value={editedBody}
                  onChange={(e) => setEditedBody(e.target.value)}
                  rows={5}
                  className="text-xs rounded border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 font-mono"
                />
              ) : (
                <pre className="text-xs text-zinc-500 whitespace-pre-wrap">
                  {JSON.stringify(approval.resolved_payload ?? approval.payload, null, 2)}
                </pre>
              )}

              {approval.simulated_send_result && (
                <p className="text-xs text-green-700 dark:text-green-400">
                  Simulated send to {JSON.stringify((approval.simulated_send_result as { sent_to?: unknown }).sent_to)}
                </p>
              )}

              {approval.status === "pending" && (
                <div className="flex gap-2 mt-1">
                  {editingId === approval.id ? (
                    <>
                      <button
                        onClick={() => submitEdit(approval)}
                        disabled={decidingId === approval.id}
                        className="rounded bg-zinc-900 dark:bg-zinc-100 text-zinc-50 dark:text-zinc-900 px-3 py-1.5 text-xs font-medium disabled:opacity-60"
                      >
                        Save &amp; approve
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        className="rounded border border-zinc-300 dark:border-zinc-700 px-3 py-1.5 text-xs font-medium"
                      >
                        Cancel edit
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => decide(approval.id, true)}
                        disabled={decidingId === approval.id}
                        className="rounded bg-zinc-900 dark:bg-zinc-100 text-zinc-50 dark:text-zinc-900 px-3 py-1.5 text-xs font-medium disabled:opacity-60"
                      >
                        Approve
                      </button>
                      {typeof approval.payload.body === "string" && (
                        <button
                          onClick={() => startEditing(approval)}
                          className="rounded border border-zinc-300 dark:border-zinc-700 px-3 py-1.5 text-xs font-medium"
                        >
                          Edit
                        </button>
                      )}
                      <button
                        onClick={() => decide(approval.id, false)}
                        disabled={decidingId === approval.id}
                        className="rounded border border-zinc-300 dark:border-zinc-700 px-3 py-1.5 text-xs font-medium disabled:opacity-60"
                      >
                        Reject
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
