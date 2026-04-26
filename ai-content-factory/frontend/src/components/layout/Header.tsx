"use client";
import { useEffect, useState } from "react";

interface HeaderProps {
  breadcrumb?: { label: string; href?: string }[];
  actions?: React.ReactNode;
}

function useClock() {
  const [display, setDisplay] = useState("");
  useEffect(() => {
    const update = () => {
      const now = new Date();
      const date = now.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
      const time = now.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
      setDisplay(`${date}  ${time}`);
    };
    update();
    const t = setInterval(update, 10_000);
    return () => clearInterval(t);
  }, []);
  return display;
}

export function Header({ breadcrumb, actions }: HeaderProps) {
  const clock = useClock();

  return (
    <header className="app-header">
      {/* Breadcrumb */}
      <div className="header-breadcrumb">
        {breadcrumb?.map((crumb, i) => (
          <span key={i} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {i > 0 && <span className="breadcrumb-sep">/</span>}
            <span className={i === (breadcrumb.length - 1) ? "breadcrumb-active" : "breadcrumb-parent"}>
              {crumb.label}
            </span>
          </span>
        ))}
      </div>

      {/* Right */}
      <div className="header-right">
        {actions}
        {clock && <span className="header-time">{clock}</span>}
      </div>
    </header>
  );
}
