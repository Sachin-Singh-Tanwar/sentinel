import React, { useCallback, useEffect, useState } from "react";
import Board from "./Board.jsx";
import Incident from "./Incident.jsx";
import Method from "./Method.jsx";
import { apiMode, loadBoard, loadIncident, loadIncidents, loadMethod } from "./data.js";

function useRoute() {
  const parse = () => {
    const parts = (window.location.hash || "#/board").replace(/^#\/?/, "").split("/");
    return { screen: parts[0] || "board", id: parts[1] ? Number(parts[1]) : null };
  };

  const [route, setRoute] = useState(parse);

  useEffect(() => {
    const onChange = () => setRoute(parse());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  return route;
}

export default function App() {
  const route = useRoute();
  const [board, setBoard] = useState(null);
  const [incidents, setIncidents] = useState(null);
  const [method, setMethod] = useState(null);
  const [incident, setIncident] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([loadBoard(), loadIncidents(), loadMethod()])
      .then(([boardData, incidentData, methodData]) => {
        if (cancelled) return;
        setBoard(boardData);
        setIncidents(incidentData);
        setMethod(methodData);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (route.screen !== "incident" || !route.id) return;
    let cancelled = false;
    setIncident(null);
    loadIncident(route.id)
      .then((data) => {
        if (!cancelled) setIncident(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [route.screen, route.id]);

  const open = useCallback((id) => {
    window.location.hash = `#/incident/${id}`;
  }, []);

  const screen = route.screen === "incident" ? "incident" : route.screen === "method" ? "method" : "board";

  return (
    <div className="min-h-screen bg-ink">
      <header className="sticky top-0 z-10 border-b border-line bg-ink/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-5 py-3">
          <a href="#/board" className="flex items-baseline gap-2">
            <span className="font-mono text-[13px] tracking-[0.22em] text-paper">SENTINEL</span>
            <span className="hidden font-mono text-[10px] text-muted sm:inline">
              drift · gate · proof
            </span>
          </a>
          <nav className="ml-auto flex items-center gap-5 font-mono text-[11px] uppercase tracking-[0.16em]">
            <a
              href="#/board"
              className={screen === "board" ? "text-paper" : "text-muted hover:text-paper"}
            >
              Board
            </a>
            <a
              href="#/method"
              className={screen === "method" ? "text-paper" : "text-muted hover:text-paper"}
            >
              Method
            </a>
          </nav>
          <span className="hidden rounded-sm border border-line px-2 py-0.5 font-mono text-[10px] text-muted md:inline">
            {apiMode ? "live API" : "static snapshot"}
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-8">
        {error && (
          <div className="mb-6 rounded-md border border-down/40 bg-down/10 px-4 py-3 font-mono text-[12px] text-down">
            {error}
          </div>
        )}

        {screen === "board" && (
          <Board board={board} incidents={incidents} onOpen={open} />
        )}
        {screen === "incident" && (
          <Incident incident={incident} onBack={() => (window.location.hash = "#/board")} />
        )}
        {screen === "method" && <Method method={method} />}
      </main>

      <footer className="mx-auto max-w-6xl px-5 pb-10 pt-4">
        <p className="border-t border-line pt-4 font-mono text-[10px] leading-relaxed text-muted">
          Public demo runs on deliberate, reversible injections. Every incident it produces is
          labelled STAGED DEMO. No login automation, no CAPTCHA solving, no proxy rotation, no
          personal data.
        </p>
      </footer>
    </div>
  );
}
