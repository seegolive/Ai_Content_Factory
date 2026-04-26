"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Video,
  CheckSquare,
  BarChart2,
  Settings,
  PanelLeftClose,
  PanelLeftOpen,
  Zap,
  LogOut,
} from "lucide-react";
import { useUIStore } from "@/stores/uiStore";
import { authApi } from "@/lib/api";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/videos", label: "Videos", icon: Video },
  { href: "/review", label: "Review Queue", icon: CheckSquare },
  { href: "/analytics", label: "Analytics", icon: BarChart2 },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarCollapsed, toggleSidebar } = useUIStore();
  const collapsed = sidebarCollapsed;

  const handleLogout = async () => {
    try { await authApi.logout(); } finally {
      if (typeof window !== "undefined") {
        localStorage.removeItem("access_token");
        window.location.href = "/login";
      }
    }
  };

  return (
    <aside className={`app-sidebar${collapsed ? " collapsed" : ""}`}>

      {/* Logo */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">
          <Zap size={14} color="var(--primary-text)" />
        </div>
        <span className="sidebar-logo-name">AI Factory</span>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        <span className="sidebar-section-label">Main</span>
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href + "/"));
          return (
            <Link
              key={href}
              href={href}
              className={`sidebar-item${active ? " active" : ""}`}
              title={collapsed ? label : undefined}
            >
              <Icon className="sidebar-item-icon" />
              <span className="sidebar-item-label">{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        <button
          onClick={handleLogout}
          className="sidebar-item"
          style={{ width: "100%", textAlign: "left" }}
          title={collapsed ? "Logout" : undefined}
        >
          <LogOut className="sidebar-item-icon" />
          <span className="sidebar-item-label">Logout</span>
        </button>

        <button
          onClick={toggleSidebar}
          className="sidebar-toggle-btn"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed
            ? <PanelLeftOpen size={14} />
            : <><PanelLeftClose size={14} /><span className="sidebar-toggle-label">Collapse</span></>
          }
        </button>
      </div>

    </aside>
  );
}
