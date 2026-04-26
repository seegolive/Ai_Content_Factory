"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Video,
  CheckSquare,
  BarChart2,
  Settings,
  ChevronLeft,
  ChevronRight,
  Factory,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/stores/uiStore";
import { authApi } from "@/lib/api";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/videos", label: "Videos", icon: Video },
  { href: "/review", label: "Review Queue", icon: CheckSquare },
  { href: "/analytics", label: "Analytics", icon: BarChart2, disabled: true },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarCollapsed, toggleSidebar } = useUIStore();

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } finally {
      if (typeof window !== "undefined") {
        localStorage.removeItem("access_token");
        window.location.href = "/login";
      }
    }
  };

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 h-full flex flex-col transition-all duration-200 z-30",
        "bg-surface border-r border-border",
        sidebarCollapsed ? "w-16" : "w-60"
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-border">
        <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
          <Factory className="w-4 h-4 text-primary" />
        </div>
        {!sidebarCollapsed && (
          <span className="font-display font-semibold text-sm text-foreground truncate">
            AI Content Factory
          </span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-4 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map(({ href, label, icon: Icon, disabled }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={disabled ? "#" : href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150",
                active
                  ? "bg-primary/10 text-primary border-l-2 border-primary"
                  : "text-foreground-muted hover:text-foreground hover:bg-muted/50",
                disabled && "opacity-40 cursor-not-allowed pointer-events-none"
              )}
              title={sidebarCollapsed ? label : undefined}
            >
              <Icon className="flex-shrink-0 w-4 h-4" />
              {!sidebarCollapsed && <span>{label}</span>}
              {!sidebarCollapsed && disabled && (
                <span className="ml-auto text-xs text-foreground-muted bg-muted px-1.5 py-0.5 rounded">
                  Soon
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Bottom: logout */}
      <div className="px-2 py-4 border-t border-border">
        <button
          onClick={handleLogout}
          className={cn(
            "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium",
            "text-foreground-muted hover:text-foreground hover:bg-muted/50 transition-all duration-150"
          )}
          title={sidebarCollapsed ? "Logout" : undefined}
        >
          <LogOut className="flex-shrink-0 w-4 h-4" />
          {!sidebarCollapsed && <span>Logout</span>}
        </button>
      </div>

      {/* Collapse toggle */}
      <button
        onClick={toggleSidebar}
        className="absolute -right-3 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-border border border-border text-foreground-muted hover:text-foreground flex items-center justify-center transition-colors"
      >
        {sidebarCollapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronLeft className="w-3 h-3" />}
      </button>
    </aside>
  );
}
