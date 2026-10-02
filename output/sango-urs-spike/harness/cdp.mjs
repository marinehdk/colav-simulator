// CDP driver for URS spike (P2-S2). Usage:
//   node cdp.mjs open <url>            # open tab, return target id
//   node cdp.mjs eval <expr-file>      # evaluate JS (file content) in first spike tab
//   node cdp.mjs shot <out.png>        # capture viewport screenshot
//   node cdp.mjs console [n]           # dump last n console messages
//   node cdp.mjs reload                # reload tab (reconnection test)
import WebSocket from "./urs-repo/WebApp/node_modules/ws/wrapper.mjs";
import { readFileSync, writeFileSync, appendFileSync } from "node:fs";

const DEBUG_PORT = 9222;
const cmd = process.argv[2];
const arg = process.argv[3];

async function getJson(path) {
  const res = await fetch(`http://127.0.0.1:${DEBUG_PORT}${path}`);
  return res.json();
}

class CDP {
  constructor(ws, logPath) { this.ws = ws; this.id = 0; this.pending = new Map(); this.consoleTail = []; this.logPath = logPath;
    ws.on("message", (data) => {
      const msg = JSON.parse(data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
      } else if (msg.method === "Runtime.consoleAPICalled") {
        const text = msg.params.args.map(a => a.value ?? a.description ?? "").join(" ");
        const line = `[console.${msg.params.type}] ${text}`;
        this.consoleTail.push(line);
        if (this.consoleTail.length > 500) this.consoleTail.shift();
        if (this.logPath) appendFileSync(this.logPath, line + "\n");
      } else if (msg.method === "Runtime.exceptionThrown") {
        const line = `[page-exception] ${JSON.stringify(msg.params.exceptionDetails?.exception?.description || msg.params.exceptionDetails?.text)}`;
        this.consoleTail.push(line);
        if (this.logPath) appendFileSync(this.logPath, line + "\n");
      }
    });
  }
  send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++this.id;
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
      setTimeout(() => { if (this.pending.has(id)) { this.pending.delete(id); reject(new Error(`timeout ${method}`)); } }, 30000);
    });
  }
}

async function findSpikeTarget() {
  const targets = await getJson("/json/list");
  return targets.find(t => t.type === "page" && t.url.includes("/spike/"));
}

async function connect() {
  const target = await findSpikeTarget();
  if (!target) throw new Error("no /spike/ tab found");
  const ws = new WebSocket(target.webSocketDebuggerUrl, { perMessageDeflate: false });
  await new Promise((res, rej) => { ws.on("open", res); ws.on("error", rej); });
  const cdp = new CDP(ws, "/tmp/urs-spike-console.log");
  await cdp.send("Runtime.enable");
  await cdp.send("Page.enable");
  return cdp;
}

if (cmd === "open") {
  const tab = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/new?${encodeURIComponent(arg)}`, { method: "PUT" }).then(r => r.json());
  console.log(JSON.stringify({ id: tab.id, url: tab.url }));
} else if (cmd === "eval") {
  const cdp = await connect();
  const expression = readFileSync(arg, "utf8");
  const r = await cdp.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true, userGesture: true });
  console.log(JSON.stringify(r.result?.value ?? r.result, null, 1));
} else if (cmd === "shot") {
  const cdp = await connect();
  const r = await cdp.send("Page.captureScreenshot", { format: "png" });
  writeFileSync(arg, Buffer.from(r.data, "base64"));
  console.log(`written ${arg}`);
} else if (cmd === "console") {
  const cdp = await connect();
  const n = parseInt(arg || "30", 10);
  console.log(cdp.consoleTail.slice(-n).join("\n"));
} else if (cmd === "reload") {
  const cdp = await connect();
  await cdp.send("Page.reload");
  console.log("reloaded");
} else {
  console.log("unknown cmd");
}
process.exit(0);
