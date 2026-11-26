import React from "react";
import { Panel, SectionLabel, Sparkline, StagedBadge, StateChip, duration, relTime } from "./ui.jsx";

export default function Board({ board, incidents, onOpen }) {
  const sources = board?.sources || [];
  const recent = (incidents?.incidents || []).slice(0, 6);

  return (
    <div className="space-y-10">
      <Panel>
        <div className="flex items-center justify-between border-b border-line px-5 py-3">
          <SectionLabel>Sources</SectionLabel>
          <span className="font-mono text-[11px] text-muted">
            snapshot {relTime(board?.generated_at)}
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="text-left font-mono text-[10px] uppercase tracking-[0.16em] text-muted">
                <th className="px-5 py-2 font-normal">source</th>
                <th className="px-4 py-2 font-normal">state</th>
                <th className="px-4 py-2 font-normal">last run</th>
                <th className="px-4 py-2 text-right font-normal">records</th>
                <th className="px-4 py-2 text-right font-normal">drift</th>
                <th className="px-4 py-2 font-normal">last 20 runs</th>
                <th className="px-5 py-2 font-normal">extractor</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((source) => {
                const last = source.last_run;
                const clickable = Boolean(source.active_incident);
                return (
                  <tr
                    key={source.id}
                    onClick={clickable ? () => onOpen(source.active_incident) : undefined}
                    className={`border-t border-line/70 ${
                      clickable ? "cursor-pointer hover:bg-line/30" : ""
                    }`}
                  >
                    <td className="px-5 py-3">
                      <div className="font-medium">{source.id}</div>
                      <div className="font-mono text-[11px] text-muted">{source.name}</div>
                    </td>
                    <td className="px-4 py-3">
                      <StateChip state={source.state} />
                    </td>
                    <td className="px-4 py-3 font-mono text-[12px] text-muted">
                      {last ? relTime(last.started_at) : "never"}
                    </td>
                    <td className="tabular px-4 py-3 text-right font-mono text-[12px]">
                      {last ? last.records : "—"}
                    </td>
                    <td className="tabular px-4 py-3 text-right font-mono text-[12px]">
                      {source.drift_score === null || source.drift_score === undefined
                        ? "—"
                        : source.drift_score.toFixed(2)}
                    </td>
                    <td className="px-4 py-3">
                      <Sparkline values={source.sparkline} />
                    </td>
                    <td className="px-5 py-3 font-mono text-[11px] text-muted">
                      {source.active_extractor || "—"}
                    </td>
                  </tr>
                );
              })}
              {!sources.length && (
                <tr>
                  <td colSpan={7} className="px-5 py-8 text-center font-mono text-[12px] text-muted">
                    no sources configured
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Panel>

      <div>
        <SectionLabel>Recent incidents</SectionLabel>
        <div className="space-y-2">
          {recent.map((incident) => (
            <button
              key={incident.id}
              onClick={() => onOpen(incident.id)}
              className="flex w-full items-center gap-4 rounded-md border border-line bg-panel/40 px-5 py-3 text-left transition hover:border-line hover:bg-panel/80"
            >
              <span className="font-mono text-[12px] text-muted">#{incident.id}</span>
              <span className="font-medium">{incident.source}</span>
              <StateChip state={incident.state} />
              {incident.staged && <StagedBadge />}
              <span className="ml-auto font-mono text-[11px] text-muted">
                {incident.duration_label === "resolved"
                  ? `MTTR ${duration(incident.duration_seconds)}`
                  : `ongoing ${duration(incident.duration_seconds)}`}
              </span>
              <span className="font-mono text-[11px] text-muted">
                {relTime(incident.drift_detected_at)}
              </span>
            </button>
          ))}
          {!recent.length && (
            <div className="rounded-md border border-dashed border-line px-5 py-8 text-center font-mono text-[12px] text-muted">
              no incidents — the last run was clean
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
