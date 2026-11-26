import React from "react";

const STATE_STYLES = {
  HEALTHY: "text-healthy border-healthy/40 bg-healthy/10",
  DRIFT: "text-drift border-drift/40 bg-drift/10",
  DOWN: "text-down border-down/40 bg-down/10",
  NEEDS_HUMAN: "text-down border-down/40 bg-down/10",
  REPAIRING: "text-verified border-verified/40 bg-verified/10",
  VERIFIED: "text-verified border-verified/40 bg-verified/10",
  UNKNOWN: "text-muted border-line bg-line/30",
};

export function StateChip({ state }) {
  const style = STATE_STYLES[state] || STATE_STYLES.UNKNOWN;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 font-mono text-[11px] tracking-widest ${style}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {state}
    </span>
  );
}

export function StagedBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-sm border border-drift/60 bg-drift/15 px-2 py-0.5 font-mono text-[11px] tracking-widest text-drift">
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-drift" />
      STAGED DEMO
    </span>
  );
}

export function Sparkline({ values = [] }) {
  if (!values.length) {
    return <span className="font-mono text-[11px] text-muted">no runs</span>;
  }
  const max = Math.max(...values, 1);
  return (
    <svg width={values.length * 7} height="22" role="img" aria-label="last 20 runs">
      {values.map((value, index) => {
        const height = Math.max(2, Math.round((value / max) * 20));
        return (
          <rect
            key={index}
            x={index * 7}
            y={22 - height}
            width="4"
            height={height}
            rx="1"
            className={value === 0 ? "fill-down/70" : "fill-healthy/70"}
          />
        );
      })}
    </svg>
  );
}

export function relTime(iso) {
  if (!iso) return "—";
  const seconds = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`;
  return `${Math.round(seconds / 86400)}d ago`;
}

export function duration(seconds) {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  if (minutes < 60) return rest ? `${minutes}m ${rest}s` : `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

export function clockTime(iso) {
  if (!iso) return "—";
  const date = new Date(iso);
  const pad = (value, size = 2) => String(value).padStart(size, "0");
  return (
    `${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}:${pad(date.getUTCSeconds())}` +
    `.${pad(date.getUTCMilliseconds(), 3)}Z`
  );
}

// Sub-second work is reported in milliseconds; anything longer in seconds. Two
// decimals, never a rounded "1s".
export function precise(seconds) {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  return `${seconds.toFixed(2)}s`;
}

export function SectionLabel({ children }) {
  return (
    <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted">{children}</div>
  );
}

export function Panel({ children, className = "" }) {
  return (
    <section className={`rounded-md border border-line bg-panel/60 ${className}`}>{children}</section>
  );
}
