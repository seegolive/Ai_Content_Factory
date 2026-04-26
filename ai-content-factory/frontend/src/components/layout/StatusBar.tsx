"use client";
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, CheckCircle, AlertCircle } from "lucide-react";
import { videosApi } from "@/lib/api";
import { cn } from "@/lib/utils";

export function StatusBar() {
  const { data: videos } = useQuery({
    queryKey: ["videos", { status: "processing" }],
    queryFn: () => videosApi.list({ status: "processing" }).then((r) => r.data),
    refetchInterval: 5_000,
  });

  const processing = videos ?? [];

  if (processing.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-xs">
      {processing.map((v) => (
        <div
          key={v.id}
          className="glass-card px-4 py-3 flex items-center gap-3 text-sm animate-fade-in"
        >
          <Loader2 className="w-4 h-4 text-primary animate-spin flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="truncate text-foreground font-medium">{v.title ?? "Processing…"}</p>
            <p className="text-foreground-muted text-xs">{v.checkpoint ?? "Queued"}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
