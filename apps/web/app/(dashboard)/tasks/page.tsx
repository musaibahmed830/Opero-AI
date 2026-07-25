"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/auth";
import { EmptyState } from "@/components/EmptyState";

interface Task {
  id: string;
  title: string;
  description: string;
  category: string;
  priority: "low" | "normal" | "high" | "critical";
  status: "open" | "done";
  confidence: number | null;
  due_at: string | null;
  created_at: string;
}

interface PaginatedTasks {
  items: Task[];
  total: number;
}

const PRIORITY_STYLES: Record<string, string> = {
  critical: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  high: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  normal: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  low: "bg-zinc-100 text-zinc-500 dark:bg-zinc-900 dark:text-zinc-500",
};

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    apiFetch<PaginatedTasks>("/v1/tasks?page_size=100")
      .then((res) => setTasks(res.items))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load tasks."));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function toggleDone(task: Task) {
    try {
      await apiFetch(`/v1/tasks/${task.id}/status`, {
        method: "POST",
        body: JSON.stringify({ status: task.status === "open" ? "done" : "open" }),
      });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update task status.");
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold">Tasks</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Tasks the Assistant creates from email commitments. A suggested due date is shown as free text in
          the description, never invented as a real deadline.
        </p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {tasks === null && !error && <p className="text-sm text-zinc-500">Loading…</p>}

      {tasks !== null && tasks.length === 0 && (
        <EmptyState
          title="No tasks yet"
          description="Tasks the Assistant extracts from action-implying emails will appear here. Try ingesting the mock inbox from the Inbox page."
        />
      )}

      {tasks !== null && tasks.length > 0 && (
        <div className="flex flex-col gap-3">
          {tasks.map((task) => (
            <div
              key={task.id}
              className="rounded-lg border border-zinc-200 dark:border-zinc-800 p-4 flex items-start gap-3"
            >
              <input
                type="checkbox"
                checked={task.status === "done"}
                onChange={() => toggleDone(task)}
                className="mt-1"
              />
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <span
                    className={`font-medium text-sm ${task.status === "done" ? "line-through text-zinc-400" : ""}`}
                  >
                    {task.title}
                  </span>
                  <span className={`text-xs rounded px-2 py-0.5 ${PRIORITY_STYLES[task.priority]}`}>
                    {task.priority}
                  </span>
                </div>
                <p className="text-xs text-zinc-500 whitespace-pre-wrap mt-1">{task.description}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
