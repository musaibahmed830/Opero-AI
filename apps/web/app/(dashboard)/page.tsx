import { EmptyState } from "@/components/EmptyState";
import { ApiStatusProbes } from "@/components/StatusProbe";

export default function OverviewPage() {
  return (
    <div className="flex flex-col gap-8 max-w-2xl">
      <div>
        <h1 className="text-2xl font-semibold">Overview</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Your AI Sales &amp; Operations Assistant&rsquo;s daily activity will summarize here once email
          ingestion and the orchestrator ship (docs/DEVELOPMENT_ROADMAP.md, Phase 1). This phase&rsquo;s
          foundation work is what the rest of this dashboard is built on.
        </p>
      </div>

      <EmptyState
        title="No activity yet"
        description="Once Gmail is connected and the orchestrator is running, today's emails handled, drafts pending, and leads created will summarize here — not before, and never with placeholder numbers."
      />

      <div>
        <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-3">System status</h2>
        <ApiStatusProbes />
      </div>
    </div>
  );
}
