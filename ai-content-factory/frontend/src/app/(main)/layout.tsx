"use client";
import { Sidebar } from "@/components/layout/Sidebar";
import { StatusBar } from "@/components/layout/StatusBar";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-main">
        {children}
      </div>
      <StatusBar />
    </div>
  );
}
