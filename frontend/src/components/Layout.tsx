import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { IntegrationStatus } from "../types";

const navItems = [
  { to: "/", label: "Home", end: true },
  { to: "/queue", label: "Queue", end: false },
  { to: "/pipeline", label: "Pipeline", end: false },
  { to: "/lanes", label: "Lanes", end: false },
  { to: "/settings", label: "Settings", end: false },
];

export function Layout() {
  const { user, signOut } = useAuth();
  const { data: status } = useQuery({
    queryKey: ["status"],
    queryFn: () => api.get<IntegrationStatus>("/api/status"),
  });

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-line bg-panel px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold tracking-tight">Beacon</span>
          <span className="badge bg-canvas text-slate-500">
            {status?.env ?? "…"}
          </span>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-slate-500">{user?.name}</span>
          <button className="btn-ghost" onClick={signOut}>
            Sign out
          </button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <nav className="w-44 shrink-0 border-r border-line bg-panel p-2">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `block rounded-md px-3 py-1.5 text-sm font-medium ${
                  isActive ? "bg-accent text-white" : "text-ink hover:bg-canvas"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <main className="min-w-0 flex-1 overflow-auto p-4">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
