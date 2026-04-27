"use client";
import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface KPICardProps {
  label: string;
  value: number | string;
  unit?: string;
  trend?: {
    value: number;
    direction: "up" | "down" | "neutral";
    period: string;
  };
  icon: ReactNode;
  accentColor?: "violet" | "teal" | "coral" | "default";
  loading?: boolean;
}

function useCountUp(target: number, duration = 1200) {
  const displayRef = useRef(0);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    if (typeof target !== "number") return;
    const start = displayRef.current;
    const diff = target - start;
    const startTime = performance.now();

    const step = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      displayRef.current = Math.round(start + diff * eased);

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(step);
      }
    };

    frameRef.current = requestAnimationFrame(step);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [target, duration]);

  return displayRef;
}

const accentMap = {
  violet: { glow: "shadow-[0_0_20px_rgba(108,99,255,0.15)]", value: "text-[#6C63FF]" },
  teal: { glow: "shadow-[0_0_20px_rgba(0,212,170,0.15)]", value: "text-[#00D4AA]" },
  coral: { glow: "shadow-[0_0_20px_rgba(255,107,107,0.15)]", value: "text-[#FF6B6B]" },
  default: { glow: "", value: "text-[#E8E8F0]" },
};

export function KPICard({
  label,
  value,
  unit,
  trend,
  icon,
  accentColor = "default",
  loading = false,
}: KPICardProps) {
  const accent = accentMap[accentColor];

  const formattedValue =
    typeof value === "number"
      ? value >= 1_000_000
        ? (value / 1_000_000).toFixed(1) + "M"
        : value >= 1_000
        ? (value / 1_000).toFixed(1) + "K"
        : value.toLocaleString()
      : value;

  if (loading) {
    return (
      <div className="kpi-card">
        <div className="skeleton" style={{ height: 12, width: 80, borderRadius: 4, marginBottom: 12 }} />
        <div className="skeleton" style={{ height: 36, width: 100, borderRadius: 4, marginBottom: 8 }} />
        <div className="skeleton" style={{ height: 20, width: 70, borderRadius: 12 }} />
      </div>
    );
  }

  const TrendIcon =
    trend?.direction === "up"
      ? TrendingUp
      : trend?.direction === "down"
      ? TrendingDown
      : Minus;

  const trendColor =
    trend?.direction === "up"
      ? "text-[#00D4AA] bg-[#00D4AA]/10"
      : trend?.direction === "down"
      ? "text-[#FF6B6B] bg-[#FF6B6B]/10"
      : "text-[#6B6B8A] bg-[#6B6B8A]/10";

  return (
    <div className={`kpi-card ${accent.glow}`}>
      <div className="kpi-card-header">
        <span className="kpi-label">{label}</span>
        <span className="kpi-icon">{icon}</span>
      </div>
      <div className={`kpi-value ${accent.value}`}>
        {formattedValue}
        {unit && <span className="kpi-unit">{unit}</span>}
      </div>
      {trend && (
        <div className={`kpi-trend ${trendColor}`}>
          <TrendIcon size={12} />
          <span>
            {trend.direction !== "neutral" ? Math.abs(trend.value).toFixed(1) + "%" : "—"}
          </span>
          <span className="kpi-trend-period">{trend.period}</span>
        </div>
      )}
    </div>
  );
}
