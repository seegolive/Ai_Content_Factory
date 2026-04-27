"use client";
import { useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { format, parseISO } from "date-fns";
import { useDailyStats } from "@/hooks/useAnalytics";

interface Props {
  channelId: string | null;
}

type Period = 7 | 30 | 90;

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="recharts-custom-tooltip">
      <p className="recharts-tooltip-date">
        {label ? format(parseISO(label), "d MMM yyyy") : ""}
      </p>
      {payload.map((entry) => (
        <p key={entry.name} style={{ color: entry.color }}>
          <span className="recharts-tooltip-label">{entry.name}:</span>{" "}
          <strong>{entry.value.toLocaleString()}</strong>
        </p>
      ))}
    </div>
  );
}

export function ViewsTrendChart({ channelId }: Props) {
  const [period, setPeriod] = useState<Period>(30);
  const { data, isLoading } = useDailyStats(channelId, period);

  const chartData =
    data?.dates.map((date, i) => ({
      date,
      Views: data.views[i] ?? 0,
      "Watch Time (min)": data.watch_time_minutes[i] ?? 0,
    })) ?? [];

  return (
    <div className="panel analytics-chart-panel">
      <div className="analytics-chart-header">
        <h3 className="analytics-section-title">Views Trend</h3>
        <div className="analytics-period-tabs">
          {([7, 30, 90] as Period[]).map((p) => (
            <button
              key={p}
              className={`analytics-period-tab${period === p ? " active" : ""}`}
              onClick={() => setPeriod(p)}
            >
              {p}D
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="skeleton" style={{ height: 200, borderRadius: 8 }} />
      ) : chartData.length === 0 ? (
        <div className="analytics-empty-chart">
          Belum ada data. Sync analytics untuk melihat tren.
        </div>
      ) : (
        <ResponsiveContainer width="100%" aspect={16 / 5}>
          <AreaChart data={chartData} margin={{ top: 10, right: 4, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="gradViews" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#6C63FF" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#6C63FF" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradWatch" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#FF6B6B" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#FF6B6B" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={(v: string) => format(parseISO(v), "d MMM")}
              tick={{ fill: "#6B6B8A", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis hide />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="Views"
              stroke="#6C63FF"
              strokeWidth={2}
              fill="url(#gradViews)"
              dot={false}
              activeDot={{ r: 4, fill: "#6C63FF" }}
            />
            <Area
              type="monotone"
              dataKey="Watch Time (min)"
              stroke="#FF6B6B"
              strokeWidth={1.5}
              fill="url(#gradWatch)"
              dot={false}
              activeDot={{ r: 3, fill: "#FF6B6B" }}
            />
            <Legend
              wrapperStyle={{ fontSize: 12, color: "#6B6B8A", paddingTop: 8 }}
              iconType="line"
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
