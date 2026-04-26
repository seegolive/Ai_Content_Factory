"use client";
import { Bell } from "lucide-react";
import { cn } from "@/lib/utils";

interface HeaderProps {
  title?: string;
  breadcrumb?: { label: string; href?: string }[];
}

export function Header({ title, breadcrumb }: HeaderProps) {
  return (
    <header className="h-14 flex items-center justify-between px-6 border-b border-border bg-surface/80 backdrop-blur-sm">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm">
        {breadcrumb?.map((crumb, i) => (
          <span key={i} className="flex items-center gap-2">
            {i > 0 && <span className="text-foreground-muted">/</span>}
            <span
              className={cn(
                i === breadcrumb.length - 1
                  ? "text-foreground font-medium"
                  : "text-foreground-muted"
              )}
            >
              {crumb.label}
            </span>
          </span>
        )) ?? (
          <span className="text-foreground font-medium font-display">{title}</span>
        )}
      </div>

      {/* Right side */}
      <div className="flex items-center gap-3">
        <button className="relative p-2 rounded-lg text-foreground-muted hover:text-foreground hover:bg-muted/50 transition-colors">
          <Bell className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
