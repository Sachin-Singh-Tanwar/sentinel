// Dev-only browser check: renders all three screens at desktop and 375px, captures
// console errors, and writes the screenshots used as evidence.
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
const screenshots = [];

const browser = await chromium.launch();

function watch(pg) {
  pg.on("console", (message) => {
    if (message.type() === "error") errors.push({ page: pg.url(), text: message.text() });
  });
  pg.on("pageerror", (error) => {
    errors.push({ page: pg.url(), text: String(error) });
  });
}

async function visit(pg, hash, ready) {
  await pg.goto(`${BASE}/${suffix}${hash}`, { waitUntil: "networkidle" });
  if (ready) await pg.locator(ready).first().waitFor({ timeout: 10000 });
  await pg.waitForTimeout(200);
}

async function shot(pg, name) {
  const path = `${OUT}/${PREFIX}${name}.png`;
  await pg.screenshot({ path, fullPage: true });
  screenshots.push(path);
}

async function noOverflow(pg, label) {
  const { scrollWidth, innerWidth } = await pg.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }));
  if (scrollWidth > innerWidth + 1) {
    failures.push(`${label}: horizontal overflow ${scrollWidth}px > ${innerWidth}px`);
  }
}

// --- desktop ---------------------------------------------------------------
const desktop = await browser.newPage({ viewport: { width: 1280, height: 900 } });
watch(desktop);

await visit(desktop, "#/board", "text=Sources");
const boardText = await desktop.locator("body").innerText();
if (!/HEALTHY|DRIFT|DOWN/.test(boardText)) failures.push("board: no state chip rendered");
if (!/a breakage it caught/i.test(boardText)) failures.push("board: caught incident is not surfaced");
if (!boardText.includes("STAGED DEMO")) failures.push("board: STAGED DEMO badge missing");
if (boardText.includes("MTTR")) failures.push("board: MTTR still displayed");
if (boardText.search(/a breakage it caught/i) > boardText.search(/sources/i)) {
  failures.push("board: caught incident is below the source table");
}
if (!/detected/i.test(boardText) || !/repaired/i.test(boardText)) {
  failures.push("board: detected/repaired split missing");
}
await shot(desktop, "desktop-board");

await visit(desktop, "#/incident/1", "text=Selector diff");
const incidentText = await desktop.locator("body").innerText();
if (!incidentText.includes("STAGED DEMO")) failures.push("incident: STAGED DEMO badge missing");
if (incidentText.includes("MTTR")) failures.push("incident: MTTR still displayed");
if (!/detected/i.test(incidentText) || !/repaired/i.test(incidentText)) {
  failures.push("incident: detected/repaired split missing");
}
if (!/scan \d+ms|scan \d+\.\d+s/.test(incidentText)) failures.push("incident: scan duration missing");
if (!/repair \d+ms|repair \d+\.\d+s/.test(incidentText)) failures.push("incident: repair duration missing");
if (!/20\/20/.test(incidentText)) failures.push("incident: golden 20/20 rows missing");
await shot(desktop, "desktop-incident");

const diffSection = desktop.locator("text=Selector diff").first();
await diffSection.scrollIntoViewIfNeeded();
await desktop.screenshot({ path: `${OUT}/${PREFIX}desktop-incident-diff.png` });

const goldenSection = desktop.locator("text=Golden set report").first();
await goldenSection.scrollIntoViewIfNeeded();
await desktop.screenshot({ path: `${OUT}/${PREFIX}desktop-incident-golden.png` });

await visit(desktop, "#/method", "text=Five signals");
const methodText = await desktop.locator("body").innerText();
if (!methodText.includes("golden set has never")) failures.push("method: limitation copy missing");
await shot(desktop, "desktop-method");

// Navigation by click, not just by URL
await visit(desktop, "#/board", "text=Incident history");
await desktop.locator("button", { hasText: "#1" }).first().click();
await desktop.waitForTimeout(400);
if (!desktop.url().includes("/incident/1")) failures.push("board: clicking an incident did not navigate");

// --- 375px ----------------------------------------------------------------
const mobile = await browser.newPage({
  viewport: { width: 375, height: 812 },
  deviceScaleFactor: 2,
});
watch(mobile);

await visit(mobile, "#/board", "text=Sources");
await noOverflow(mobile, "mobile board");
const mobileBoard = await mobile.locator("body").innerText();
if (!/a breakage it caught/i.test(mobileBoard)) failures.push("mobile board: caught incident missing");
if (!mobileBoard.includes("STAGED DEMO")) failures.push("mobile board: STAGED DEMO badge missing");
await shot(mobile, "mobile-board");

await visit(mobile, "#/incident/1", "text=Selector diff");
await noOverflow(mobile, "mobile incident");
await shot(mobile, "mobile-incident");

await visit(mobile, "#/method", "text=Five signals");
await noOverflow(mobile, "mobile method");
await shot(mobile, "mobile-method");

await browser.close();

const report = {
  mode: API ? "live API" : "static snapshot",
  base: BASE,
  console_errors: errors,
  failures,
  screenshots,
};
writeFileSync(`${OUT}/${PREFIX}check.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));

if (errors.length || failures.length) process.exit(1);
