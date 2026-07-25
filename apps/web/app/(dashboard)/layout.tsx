"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { AuthUser, getCurrentUser, getToken, logout } from "@/lib/auth";

const NAV_ITEMS = [
  { label: "Overview", href: "/" },
  { label: "Inbox", href: "/inbox" },
  { label: "Tasks", href: "/tasks" },
  { label: "Leads", href: "/leads" },
  { label: "Approvals", href: "/approvals" },
  { label: "Knowledge", href: "/knowledge" },
  { label: "Reports", href: "/reports" },
  { label: "Activity Log", href: "/activity-log" },
  { label: "Settings", href: "/settings" },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/sign-in");
      return;
    }
    getCurrentUser()
      .then(setUser)
      .catch(() => router.replace("/sign-in"))
      .finally(() => setChecked(true));
  }, [router]);

  if (!checked) {
    return <div className="flex min-h-screen items-center justify-center text-sm text-zinc-500">Loading…</div>;
  }

  return (
    <div className="flex min-h-screen bg-zinc-50 dark:bg-zinc-950">
      <aside className="w-56 shrink-0 border-r border-zinc-200 dark:border-zinc-800 p-4 flex flex-col">
        <div className="mb-6 text-lg font-semibold">Opero AI</div>
        <nav className="flex flex-col gap-1 text-sm flex-1">
          {NAV_ITEMS.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className={`rounded px-2 py-1.5 hover:bg-zinc-200/60 dark:hover:bg-zinc-800/60 ${
                pathname === item.href ? "bg-zinc-200/60 dark:bg-zinc-800/60 font-medium" : ""
              }`}
            >
              {item.label}
            </a>
          ))}
        </nav>
      </aside>
      <div className="flex-1 flex flex-col">
        <header className="h-14 shrink-0 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between px-6">
          <span className="text-sm text-zinc-500">{user?.email}</span>
          <button
            onClick={() => {
              logout();
              router.replace("/sign-in");
            }}
            className="text-sm text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
          >
            Sign out
          </button>
        </header>
        <main className="flex-1 p-8">{children}</main>
      </div>
    </div>
  );
}
