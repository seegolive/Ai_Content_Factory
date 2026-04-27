"use client";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { useGamePerformance } from "@/hooks/useAnalytics";
import { Flame, TrendingUp, AlertCircle } from "lucide-react";
import type { GamePerformance } from "@/types/analytics";

interface Props {
  channelId: string | null;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ payload: GamePerformance }>;
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const g = payload[0].payload;
  return (
    <div className="recharts-custom-tooltip">
      <p style={{ color: "#E8E8F0", fontWeight: 600, marginBottom: 4 }}>{g.name}</p>
      <p style={{ color: "#6B6B8A", fontSize: 12 }}>Avg views: <strong style={{ color: "#E8E8F0" }}>{g.avg_views}</strong></p>
      <p style={{ color: "#6B6B8A", fontSize: 12 }}>Avg CTR: <strong style={{ color: "#00D4AA" }}>{(g.avg_ctr * 100).toFixed(1)}%</strong></p>
      <p style={{ color: "#6B6B8A", fontSize: 12 }}>Videos: <strong style={{ color: "#E8E8F0" }}>{g.video_count}</strong></p>
      <p style={{ color: "#6B6B8A", fontSize: 12, marginTop: 4 }}>{g.recommendation}</p>
    </div>
  );
}

const BAR_COLORS = ["#6C63FF", "#7B75FF", "#8A87FF", "#9999FF", "#B0AFFF"];

function GameBadge({ game }: { game: GamePerformance }) {
  if (game.trend === "up") {
    return (
      <span className="game-badge hot">
        <Flame size={10} /> Top
      </span>
    );
  }
  if (game.avg_ctr < 0.03) {
    return (
      <span className="game-badge warn">
        <AlertCircle size={10} /> Optimize
      </span>
    );
  }
  return (
    <span className="game-badge stable">
      <TrendingUp size={10} /> Stable
    </span>
  );
}

export function GamePerformanceChart({ channelId }: Props) {
  const { data, isLoading } = useGamePerformance(channelId);

  if (isLoading) {
    return (
      <div className="panel" style={{ height: 280 }}>
        <div className="skeleton" style={{ height: "100%", borderRadius: 8 }} />
      </div>
    );
  }

  const games = data?.games ?? [];

  return (
    <div className="panel analytics-chart-panel">
      <h3 className="analytics-section-title">Game Performance</h3>
      {games.length === 0 ? (
        <p className="analytics-empty-chart">{data?.message ?? "Belum ada data game"}</p>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={Math.max(160, games.length * 44)}>
            <BarChart
              data={games}
              layout="vertical"
              margin={{ top: 0, right: 40, left: 0, bottom: 0 }}
            >
              <XAxis type="number" hide />
              <YAxis
                type="category"
                dataKey="name"
                width={140}
                tick={{ fill: "#E8E8F0", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
              <Bar dataKey="avg_views" radius={[0, 4, 4, 0]} label={{ position: "right", fill: "#6B6B8A", fontSize: 11 }}>
                {games.map((_, i) => (
                  <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          {/* Recommendations */}
          <div className="game-recs">
            {games.map((g) => (
              <div key={g.name} className="game-rec-row">
                <GameBadge game={g} />
                <span className="game-rec-name">{g.name}</span>
                <span className="game-rec-text">{g.recommendation}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
