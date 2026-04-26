"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { StatusBar } from "@/components/layout/StatusBar";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();

  useEffect(() => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("access_token");
      if (!token) router.replace("/login");
    }
  }, [router]);

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-main">
        {children}
        <StatusBar />
      </div>
    </div>
  );
}
