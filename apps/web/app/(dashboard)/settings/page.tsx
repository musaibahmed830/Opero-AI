"use client";

import { useEffect, useState } from "react";
import { apiFetch, AuthUser, getCurrentUser } from "@/lib/auth";
import { EmptyState } from "@/components/EmptyState";

interface EmailAccount {
  id: string;
  email_address: string;
  connected_at: string;
  last_synced_at: string | null;
}

export default function SettingsPage() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accounts, setAccounts] = useState<EmailAccount[] | null>(null);

  useEffect(() => {
    getCurrentUser().then(setUser).catch(() => {});
    apiFetch<EmailAccount[]>("/v1/integrations/gmail/accounts")
      .then(setAccounts)
      .catch(() => setAccounts([]));
  }, []);

  return (
    <div className="flex flex-col gap-8 max-w-2xl">
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="mt-1 text-sm text-zinc-500">Organization details and connected integrations.</p>
      </div>

      <section>
        <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-3">Account</h2>
        <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 p-4 text-sm">
          <div className="flex justify-between py-1">
            <span className="text-zinc-500">Email</span>
            <span>{user?.email ?? "…"}</span>
          </div>
          <div className="flex justify-between py-1">
            <span className="text-zinc-500">Organization ID</span>
            <span className="font-mono text-xs">{user?.organization_id ?? "…"}</span>
          </div>
        </div>
      </section>

      <section>
        <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-3">
          Connected integrations
        </h2>
        {accounts === null && <p className="text-sm text-zinc-500">Loading…</p>}
        {accounts !== null && accounts.length === 0 && (
          <EmptyState
            title="No integrations connected"
            description="Connecting Gmail requires a Google Cloud OAuth client configured on the API (GOOGLE_OAUTH_CLIENT_ID/SECRET) — see the root README. Once configured, connecting an account from this page is Phase 1+ UI work; the API endpoints already exist."
          />
        )}
        {accounts !== null && accounts.length > 0 && (
          <div className="flex flex-col gap-2">
            {accounts.map((account) => (
              <div
                key={account.id}
                className="rounded-lg border border-zinc-200 dark:border-zinc-800 p-4 text-sm flex justify-between"
              >
                <span>{account.email_address}</span>
                <span className="text-zinc-500">
                  {account.last_synced_at
                    ? `Last synced ${new Date(account.last_synced_at).toLocaleString()}`
                    : "Never synced"}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
