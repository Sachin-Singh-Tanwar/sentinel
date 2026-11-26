import React from "react";
import { Panel, SectionLabel } from "./ui.jsx";

export default function Method({ method }) {
  if (!method) {
    return <div className="font-mono text-[12px] text-muted">loading method…</div>;
  }

  return (
    <div className="space-y-10">
      <div className="max-w-2xl">
        <h1 className="text-xl font-medium tracking-tight">How a repair gets trusted</h1>
        <p className="mt-3 text-[14px] leading-relaxed text-muted">
          Sentinel watches public sources, and when the shape of one changes it says so. A
          repair is proposed, then measured against 20 archived records that were captured
          once and frozen. The model does not decide. The golden set decides.
        </p>
      </div>

      <div>
        <SectionLabel>Five signals</SectionLabel>
        <Panel className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="text-left font-mono text-[10px] uppercase tracking-[0.16em] text-muted">
                <th className="px-5 py-2 font-normal">signal</th>
                <th className="px-4 py-2 font-normal">condition</th>
                <th className="px-5 py-2 font-normal">state</th>
              </tr>
            </thead>
            <tbody>
              {(method.signals || []).map((signal) => (
                <tr key={signal.name} className="border-t border-line/70">
                  <td className="px-5 py-2 font-mono text-[12px]">{signal.name}</td>
                  <td className="px-4 py-2 text-[13px] text-muted">{signal.condition}</td>
                  <td className="px-5 py-2 font-mono text-[11px] text-drift">{signal.state}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="border-t border-line px-5 py-3 font-mono text-[11px] text-muted">
            evaluated over the last {method.window?.records} records · record drop against a{" "}
            {method.window?.runs_median}-run median · {method.window?.down_streak} consecutive runs
            for DOWN
          </div>
        </Panel>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <SectionLabel>State machine</SectionLabel>
          <Panel className="px-5 py-4">
            <pre className="overflow-x-auto font-mono text-[11px] leading-relaxed text-muted">
              {method.state_machine}
            </pre>
          </Panel>
        </div>
        <div>
          <SectionLabel>Gate</SectionLabel>
          <Panel className="space-y-2 px-5 py-4 text-[13px]">
            <div className="flex justify-between gap-4">
              <span className="text-muted">field accuracy</span>
              <span className="font-mono">
                ≥ {(method.gate?.field_accuracy_min * 100).toFixed(0)}%
              </span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-muted">regressions allowed</span>
              <span className="font-mono">{method.gate?.require_zero_regression ? "0" : "—"}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-muted">decided by</span>
              <span className="font-mono text-healthy">{method.gate?.decided_by}</span>
            </div>
          </Panel>
        </div>
      </div>

      <div>
        <SectionLabel>Limitation</SectionLabel>
        <Panel className="border-drift/25 bg-drift/5 px-5 py-4">
          <p className="max-w-3xl text-[14px] leading-relaxed text-paper/90">
            {method.limitation}
          </p>
        </Panel>
      </div>
    </div>
  );
}
