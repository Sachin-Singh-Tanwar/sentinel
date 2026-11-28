import React, { useState } from "react";
import { Panel, SectionLabel, StagedBadge, StateChip, clockTime, precise, relTime } from "./ui.jsx";

function Meta({ label, children }) {
  return (
    <div>
      <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted">{label}</div>
      <div className="mt-1 font-mono text-[13px]">{children}</div>
    </div>
  );
}

const KIND_STYLES = {
  drift_detected: "border-drift bg-drift",
  gate_pass: "border-healthy bg-healthy",
  gate_reject: "border-down bg-down",
  invalidated: "border-line bg-muted",
  run: "border-line bg-muted",
};

const TIMELINE_PREVIEW = 5;

function IncidentTimeline({ events }) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? events : events.slice(0, TIMELINE_PREVIEW);
  const hidden = events.length - visible.length;

  return (
    <div>
      <SectionLabel>Timeline</SectionLabel>
      <ol className="space-y-0">
        {visible.map((event, index) => (
          <li key={index} className="flex gap-4 border-l border-line py-2 pl-4">
            <span
              className={`mt-1.5 h-2 w-2 shrink-0 -translate-x-[21px] rounded-full border ${
                KIND_STYLES[event.kind] || "border-line bg-muted"
              }`}
            />
            <span className="w-16 shrink-0 font-mono text-[11px] text-muted">
              {relTime(event.at)}
            </span>
            <span className="text-[13px]">{event.label}</span>
          </li>
        ))}
        {!events.length && (
          <li className="font-mono text-[12px] text-muted">no events recorded</li>
        )}
      </ol>
      {events.length > TIMELINE_PREVIEW && (
        <button
          type="button"
          onClick={() => setExpanded((current) => !current)}
          aria-expanded={expanded}
          className="mt-3 font-mono text-[10px] uppercase tracking-[0.16em] text-muted hover:text-paper"
        >
          {expanded ? "show less" : `show more · ${hidden} more`}
        </button>
      )}
    </div>
  );
}

export default function Incident({ incident, onBack }) {
  if (!incident) {
    return <div className="font-mono text-[12px] text-muted">loading incident…</div>;
  }

  const report = incident.gate_report;
  const diff = incident.diff;
  const fields = report?.fields || {};
  const fieldNames = Object.keys(fields);

  return (
    <div className="space-y-8">
      <button
        onClick={onBack}
        className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted hover:text-paper"
      >
        ← board
      </button>

      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-medium tracking-tight">
          incident #{incident.id}
          <span className="ml-2 font-mono text-[13px] text-muted">{incident.source}</span>
        </h1>
        <StateChip state={incident.state} />
        {incident.staged && <StagedBadge />}
      </div>

      {incident.staged && (
        <p className="rounded-md border border-drift/30 bg-drift/5 px-4 py-3 text-[13px] text-drift/90">
          This incident was produced by a deliberate, reversible layout injection. It is a
          staged demonstration, not a real outage.
        </p>
      )}

      {incident.state === "INVALIDATED" && (
        <p className="rounded-md border border-line bg-line/10 px-4 py-3 text-[13px] text-muted">
          {incident.summary || "Closed: configuration defect, not source drift. No repair was performed."}
        </p>
      )}

      <Panel className="grid grid-cols-2 gap-6 px-5 py-4 md:grid-cols-4">
        <Meta label="detected">
          {clockTime(incident.drift_detected_at)}
          <span className="mt-0.5 block text-[10px] text-muted">
            scan {precise(incident.detection_seconds)} · {relTime(incident.drift_detected_at)}
          </span>
        </Meta>
        <Meta label={incident.state === "INVALIDATED" ? "CLOSED" : "repaired"}>
          {incident.verified_at ? clockTime(incident.verified_at) : "—"}
          <span className="mt-0.5 block text-[10px] text-muted">
            {incident.state === "INVALIDATED"
              ? "closed — · no repair performed"
              : `repair ${precise(incident.repair_seconds)}${
                  incident.verified_at ? ` · ${relTime(incident.verified_at)}` : " · ongoing"
                }`}
          </span>
        </Meta>
        <Meta label="gate">
          {report ? `${report.decision} ${(report.field_accuracy * 100).toFixed(2)}%` : "not run"}
          <span className="mt-0.5 block text-[10px] text-muted">
            {report ? `${report.records_found}/${report.records_expected} records` : "—"}
          </span>
        </Meta>
        <Meta label="extractor">
          {incident.before_version || "—"}
          {incident.after_version ? ` → ${incident.after_version}` : ""}
        </Meta>
      </Panel>

      <IncidentTimeline events={incident.timeline || []} />

      <div>
        <SectionLabel>Selector diff — before → after</SectionLabel>
        <Panel className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="text-left font-mono text-[10px] uppercase tracking-[0.16em] text-muted">
                <th className="px-5 py-2 font-normal">field</th>
                <th className="px-4 py-2 font-normal">before</th>
                <th className="px-4 py-2 font-normal">after</th>
              </tr>
            </thead>
            <tbody>
              {diff ? (
                <>
                  <tr className="border-t border-line/70">
                    <td className="px-5 py-2 font-mono text-[12px] text-muted">container</td>
                    <td className="px-4 py-2 font-mono text-[11px] text-down/80">
                      {diff.container?.before || "—"}
                    </td>
                    <td className="px-4 py-2 font-mono text-[11px] text-healthy/90">
                      {diff.container?.after || "—"}
                    </td>
                  </tr>
                  {Object.entries(diff.fields || {}).map(([name, change]) => (
                    <tr key={name} className="border-t border-line/70">
                      <td className="px-5 py-2 font-mono text-[12px] text-muted">{name}</td>
                      <td
                        className={`px-4 py-2 font-mono text-[11px] ${
                          change.changed ? "text-down/80" : "text-muted"
                        }`}
                      >
                        {change.before || "—"}
                      </td>
                      <td
                        className={`px-4 py-2 font-mono text-[11px] ${
                          change.changed ? "text-healthy/90" : "text-muted"
                        }`}
                      >
                        {change.after || "—"}
                      </td>
                    </tr>
                  ))}
                </>
              ) : (
                <tr>
                  <td colSpan={3} className="px-5 py-6 text-center font-mono text-[12px] text-muted">
                    no diff yet — the gate has not run on this incident
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Panel>
      </div>

      <div>
        <SectionLabel>
          Golden set report — {report ? `${report.decision} at ${(report.field_accuracy * 100).toFixed(2)}%` : "not run"}
        </SectionLabel>
        <Panel className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="text-left font-mono text-[10px] uppercase tracking-[0.16em] text-muted">
                <th className="px-5 py-2 font-normal">field</th>
                <th className="px-4 py-2 text-right font-normal">matched</th>
                <th className="px-4 py-2 font-normal">accuracy</th>
                <th className="px-5 py-2 font-normal">note</th>
              </tr>
            </thead>
            <tbody>
              {fieldNames.map((name) => {
                const field = fields[name];
                const absent = field.null_in_golden === field.total;
                return (
                  <tr key={name} className="border-t border-line/70">
                    <td className="px-5 py-2 font-mono text-[12px]">{name}</td>
                    <td className="tabular px-4 py-2 text-right font-mono text-[12px]">
                      {field.correct}/{field.total}
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-28 overflow-hidden rounded-full bg-line">
                          <div
                            className={`h-full ${
                              field.accuracy >= 0.95 ? "bg-healthy" : "bg-down"
                            }`}
                            style={{ width: `${Math.round(field.accuracy * 100)}%` }}
                          />
                        </div>
                        <span className="tabular font-mono text-[11px] text-muted">
                          {(field.accuracy * 100).toFixed(0)}%
                        </span>
                      </div>
                    </td>
                    <td className="px-5 py-2 font-mono text-[11px] text-muted">
                      {absent ? "not published upstream" : ""}
                    </td>
                  </tr>
                );
              })}
              {!fieldNames.length && (
                <tr>
                  <td colSpan={4} className="px-5 py-6 text-center font-mono text-[12px] text-muted">
                    the gate has not evaluated a candidate for this incident
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          {report && (
            <div className="flex flex-wrap items-center gap-x-6 gap-y-1 border-t border-line px-5 py-3 font-mono text-[11px] text-muted">
              <span>threshold ≥ {(report.threshold * 100).toFixed(0)}%</span>
              <span>records {report.records_found}/{report.records_expected}</span>
              <span>regressions {report.regressions?.length || 0}</span>
              <span>{report.decision === "PASS" ? "applied" : "nothing applied"}</span>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
