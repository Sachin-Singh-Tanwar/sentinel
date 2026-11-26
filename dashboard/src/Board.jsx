import React from "react";
import {
  Panel,
  SectionLabel,
  Sparkline,
  StagedBadge,
  StateChip,
  clockTime,
  precise,
  relTime,
} from "./ui.jsx";

function Meta({ label, value, sub }) {
  return (
    <div className="min-w-0">
      <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted">{label}</div>
      <div className="mt-1 truncate font-mono text-[12px]">{value}</div>
      {sub && <div className="mt-0.5 truncate font-mono text-[10px] text-muted">{sub}</div>}
    </div>
  );
}

// The product is "it catches breakage", so the caught breakage is the first thing
// on the page, not a row at the bottom. Incident #1 is the canonical staged
// walkthrough and stays featured as later demo runs accumulate behind it.
function CaughtIncident({ incident, onOpen }) {
  if (!incident) {
    return (
      <Panel className="px-5 py-6">
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
          No breakage caught yet
        </div>
        <p className="mt-2 text-[13px] text-muted">
          The next layout change on a monitored source will open an incident here.
        </p>
      </Panel>
    );
  }

  const report = incident.gate_report;
  const verified = Boolean(incident.verified_at);
  const accuracy = report ? `${(report.field_accuracy * 100).toFixed(2)}%` : "—";

  return (
    <Panel className="overflow-hidden border-drift/30">
      <div className="flex flex-col gap-5 px-5 py-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-drift">
              A breakage it caught
            </span>
            {incident.staged && <StagedBadge />}
          </div>
          <h2 className="mt-2 text-lg font-medium tracking-tight">
            incident #{incident.id}
            <span className="ml-2 font-mono text-[12px] text-muted">{incident.source}</span>
          </h2>
          <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-muted">
            {verified
              ? `The layout changed under ${incident.before_version}. Drift fired on the next run, ` +
                `a candidate extractor was gated at ${accuracy} on the frozen golden set, and ` +
                `${incident.after_version} was applied.`
              : `The layout changed under ${incident.before_version}. The gate rejected the ` +
                `candidate at ${accuracy} — nothing was applied.`}
          </p>
        </div>
        <button
          onClick={() => onOpen(incident.id)}
          className="shrink-0 rounded-sm border border-drift/50 bg-drift/10 px-3 py-2 font-mono text-[11px] uppercase tracking-[0.14em] text-drift transition hover:bg-drift/20"
        >
          Open incident #{incident.id} →
        </button>
      </div>

      <div className="grid grid-cols-2 gap-x-6 gap-y-4 border-t border-line px-5 py-4 md:grid-cols-4">
        <Meta
          label="detected"
          value={clockTime(incident.drift_detected_at)}
          sub={`scan ${precise(incident.detection_seconds)}`}
        />
        <Meta
          label="repaired"
          value={clockTime(incident.verified_at)}
          sub={`repair ${precise(incident.repair_seconds)}`}
        />
        <Meta
          label="gate"
          value={report ? `${report.decision} ${accuracy}` : "not run"}
          sub={report ? `${report.records_found}/${report.records_expected} records` : "—"}
        />
        <Meta
          label="extractor"
          value={`${incident.before_version || "—"} → ${incident.after_version || "—"}`}
          sub={incident.staged ? "staged, reversible" : "live"}
        />
      </div>
    </Panel>
  );
}

export default function Board({ board, incidents, onOpen }) {
  const sources = board?.sources || [];
  const all = incidents?.incidents || [];
  const staged = all.filter((incident) => incident.staged);
  const featured = staged.length ? staged[staged.length - 1] : all[all.length - 1] || null;
  const recent = all.slice(0, 6);

  return (
    <div className="space-y-8">
      <CaughtIncident incident={featured} onOpen={onOpen} />

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
                <th className="whitespace-nowrap px-4 py-2 font-normal">state</th>
                <th className="hidden px-4 py-2 font-normal md:table-cell">last run</th>
                <th className="hidden px-4 py-2 text-right font-normal md:table-cell">records</th>
                <th className="hidden px-4 py-2 text-right font-normal md:table-cell">drift</th>
                <th className="hidden px-4 py-2 font-normal md:table-cell">last 20 runs</th>
                <th className="hidden px-5 py-2 font-normal md:table-cell">extractor</th>
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
                      <div className="break-all font-mono text-[11px] text-muted">{source.name}</div>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <StateChip state={source.state} />
                    </td>
                    <td className="hidden px-4 py-3 font-mono text-[12px] text-muted md:table-cell">
                      {last ? relTime(last.started_at) : "never"}
                    </td>
                    <td className="tabular hidden px-4 py-3 text-right font-mono text-[12px] md:table-cell">
                      {last ? last.records : "—"}
                    </td>
                    <td className="tabular hidden px-4 py-3 text-right font-mono text-[12px] md:table-cell">
                      {source.drift_score === null || source.drift_score === undefined
                        ? "—"
                        : source.drift_score.toFixed(2)}
                    </td>
                    <td className="hidden px-4 py-3 md:table-cell">
                      <Sparkline values={source.sparkline} />
                    </td>
                    <td className="hidden px-5 py-3 font-mono text-[11px] text-muted md:table-cell">
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
        <SectionLabel>Incident history</SectionLabel>
        <div className="space-y-2">
          {recent.map((incident) => (
            <button
              key={incident.id}
              onClick={() => onOpen(incident.id)}
              className="flex w-full flex-wrap items-center gap-x-4 gap-y-2 rounded-md border border-line bg-panel/40 px-5 py-3 text-left transition hover:bg-panel/80"
            >
              <span className="font-mono text-[12px] text-muted">#{incident.id}</span>
              <span className="font-medium">{incident.source}</span>
              <StateChip state={incident.state} />
              {incident.staged && <StagedBadge />}
              <span className="ml-auto flex items-center gap-4 font-mono text-[11px] text-muted">
                <span>detected {relTime(incident.drift_detected_at)}</span>
                <span className={incident.verified_at ? "text-verified" : "text-drift"}>
                  {incident.verified_at ? "repaired" : "ongoing"}
                </span>
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
