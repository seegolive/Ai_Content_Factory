import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDuration(seconds?: number): string {
  if (!seconds) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function formatFileSize(mb?: number): string {
  if (!mb) return "—";
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(2)} GB`;
}

export function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

export function getStatusColor(status: string): string {
  const map: Record<string, string> = {
    queued: "text-foreground-muted bg-muted",
    processing: "text-primary bg-primary/10",
    review: "text-warning bg-warning/10",
    done: "text-secondary bg-secondary/10",
    error: "text-destructive bg-destructive/10",
    approved: "text-secondary bg-secondary/10",
    rejected: "text-destructive bg-destructive/10",
    pending: "text-foreground-muted bg-muted",
    passed: "text-secondary bg-secondary/10",
    failed: "text-destructive bg-destructive/10",
  };
  return map[status] ?? "text-foreground-muted bg-muted";
}

export function getViralScoreColor(score?: number): string {
  if (!score) return "text-foreground-muted";
  if (score >= 80) return "text-secondary";
  if (score >= 60) return "text-warning";
  return "text-destructive";
}
