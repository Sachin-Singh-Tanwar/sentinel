// Data source. If an API base is supplied (?api=… or VITE_API_BASE at build time) the
// dashboard reads the live FastAPI process. Otherwise it reads the static JSON that CI
// publishes to the `data` branch — the public demo never depends on a running server.

const params = new URLSearchParams(window.location.search);
const API = (params.get("api") || import.meta.env.VITE_API_BASE || "").replace(/\/$/, "");
const base = import.meta.env.BASE_URL;

export const apiMode = Boolean(API);

async function getJSON(url) {
  const response = await fetch(url, { headers: { accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`${url} responded ${response.status}`);
  }
  return response.json();
}

export const loadBoard = () => (API ? getJSON(`${API}/health`) : getJSON(`${base}data/board.json`));
export const loadIncidents = () =>
  API ? getJSON(`${API}/incidents`) : getJSON(`${base}data/incidents.json`);
export const loadIncident = (id) =>
  API ? getJSON(`${API}/incidents/${id}`) : getJSON(`${base}data/incidents/${id}.json`);
export const loadMethod = () => (API ? getJSON(`${API}/method`) : getJSON(`${base}data/method.json`));
