// Dev-only browser check: renders all three screens, captures console errors, writes
// screenshots. Run against the static build and against the live API.
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";

const BASE = process.env.BASE || "http://127.0.0.1:4173";
const API = process.env.API || "";
const OUT = process.env.OUT || "../../docs/screenshots";
const PREFIX = process.env.PREFIX || "";

mkdirSync(OUT, { recursive: true });

const suffix = API ? `?api=${encodeURIComponent(API)}` : "";
const errors = [];
const failures = [];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

page.on("console", (message) => {
  if (message.type() === "error") errors.push({ page: page.url(), text: message.text() });
});
page.on("pageerror", (error) => {
  errors.push({ page: page.url(), text: String(error) });
});

async function visit(hash, ready) {
  await page.goto(`${BASE}/${suffix}${hash}`, { waitUntil: "networkidle" });
  if (ready) await page.locator(ready).first().waitFor({ timeout: 10000 });
  await page.waitForTimeout(200);
}

async function shot(name, options = {}) {
  const path = `${OUT}/${PREFIX}${name}.png`;
  await page.screenshot({ path, fullPage: options.fullPage ?? true });
  return path;
}

// Board
await visit("#/board", "text=Sources");
const boardText = await page.locator("body").innerText();
if (!/HEALTHY|DRIFT|DOWN/.test(boardText)) failures.push("board: no state chip rendered");
await shot("board");

// Incident — full page, then the two evidence sections on their own
await visit("#/incident/1", "text=Selector diff");
const incidentText = await page.locator("body").innerText();
if (!incidentText.includes("STAGED DEMO")) failures.push("incident: STAGED DEMO badge missing");
if (!/MTTR/.test(incidentText)) failures.push("incident: MTTR missing");
if (!/20\/20/.test(incidentText)) failures.push("incident: golden 20/20 rows missing");
await shot("incident");

const diffSection = page.locator("text=Selector diff").first();
await diffSection.scrollIntoViewIfNeeded();
await page.screenshot({ path: `${OUT}/${PREFIX}incident-diff.png` });

const goldenSection = page.locator("text=Golden set report").first();
await goldenSection.scrollIntoViewIfNeeded();
await page.screenshot({ path: `${OUT}/${PREFIX}incident-golden.png` });

// Method
await visit("#/method", "text=Five signals");
const methodText = await page.locator("body").innerText();
if (!methodText.includes("golden set has never")) failures.push("method: limitation copy missing");
await shot("method");

// Navigation by click, not just by URL
await visit("#/board", "text=Recent incidents");
await page.locator("text=Recent incidents").first().waitFor();
await page.locator("button", { hasText: "#1" }).first().click();
await page.waitForTimeout(400);
if (!page.url().includes("/incident/1")) failures.push("board: clicking an incident did not navigate");

await browser.close();

const report = {
  mode: API ? "live API" : "static snapshot",
  base: BASE,
  console_errors: errors,
  failures,
  screenshots: [`${OUT}/${PREFIX}board.png`, `${OUT}/${PREFIX}incident.png`, `${OUT}/${PREFIX}method.png`],
};
writeFileSync(`${OUT}/${PREFIX}check.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));

if (errors.length || failures.length) process.exit(1);
