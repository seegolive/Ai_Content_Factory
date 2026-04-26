"use client";
import { Sidebar } from "@/components/layout/Sidebar";
import { StatusBar } from "@/components/layout/StatusBar";
import { useUIStore } from "@/stores/uiStore";
import { cn } from "@/lib/utils";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const sidebarCollapsed = useUIStore((s) => s.sidebarCollapsed);

  return (
    <div className="min-h-screen bg-background flex">
      <Sidebar />
      <main
        className={cn(
          "flex-1 flex flex-col min-h-screen transition-all duration-200",
          sidebarCollapsed ? "ml-16" : "ml-60"
        )}
      >
        {children}
      </main>
      <StatusBar />
    </div>
  );
}
