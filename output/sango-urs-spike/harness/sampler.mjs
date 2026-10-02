// Precise latency sampler: captures screenshot N times, recording host clock
// immediately before/after each CDP captureScreenshot call (window ~10-30ms).
// Usage: node sampler.mjs <outPrefix> <count>
import WebSocket from "./urs-repo/WebApp/node_modules/ws/wrapper.mjs";
import { writeFileSync } from "node:fs";

const [, , outPrefix, countArg] = process.argv;
const count = parseInt(countArg || "5", 10);

async function getJson(path) { return (await fetch(`http://127.0.0.1:9222${path}`)).json(); }
const targets = await getJson("/json/list");
const target = targets.find(t => t.type === "page" && t.url.includes("/spike/"));
if (!target) throw new Error("no /spike/ tab");
const ws = new WebSocket(target.webSocketDebuggerUrl, { perMessageDeflate: false });
await new Promise((res, rej) => { ws.on("open", res); ws.on("error", rej); });
let id = 0; const pending = new Map();
ws.on("message", (data) => {
  const msg = JSON.parse(data);
  if (msg.id && pending.has(msg.id)) { const p = pending.get(msg.id); pending.delete(msg.id); p(msg.result); }
});
function send(method, params = {}) {
  return new Promise((resolve) => { const i = ++id; pending.set(i, resolve); ws.send(JSON.stringify({ id: i, method, params })); });
}

for (let n = 1; n <= count; n++) {
  const before = Date.now();
  const r = await send("Page.captureScreenshot", { format: "png" });
  const after = Date.now();
  writeFileSync(`${outPrefix}-${n}.png`, Buffer.from(r.data, "base64"));
  // local wall clock string for the capture window
  const fmt = (ms) => { const d = new Date(ms); return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}.${String(d.getMilliseconds()).padStart(3, "0")}`; };
  console.log(JSON.stringify({ n, before: fmt(before), after: fmt(after), beforeMs: before, afterMs: after }));
  await new Promise(r2 => setTimeout(r2, 1500));
}
process.exit(0);
