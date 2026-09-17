"""PROTOTYPE: recorded Colav poses -> original Gemini gRPC service, with local controls."""
import argparse
import bisect
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import sys
import threading
import time
from urllib.parse import parse_qs, urlparse

import grpc
sys.path.insert(0, str(Path(__file__).parent / "generated"))
import simulation_pb2 as pb
import simulation_pb2_grpc as rpc

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--address", default="127.0.0.1:12346")
parser.add_argument("--port", type=int, default=8127)
args = parser.parse_args()
data = json.loads((ROOT / "data/replay.json").read_text())
frames = data["frames"]
times = [frame["time"] for frame in frames]
lock = threading.Lock()
state = {"playing": False, "rate": 8.0, "time": 0.0, "anchor": time.monotonic(),
         "revision": 0, "ack_time": -1.0, "connected": False,
         "error": "Waiting for Unity Play mode", "sent": 0, "capture": 0}
outputs = ROOT / "outputs"
outputs.mkdir(exist_ok=True)

def current_time():
    elapsed = (time.monotonic() - state["anchor"]) * state["rate"] if state["playing"] else 0
    return min(data["duration"], max(0.0, state["time"] + elapsed))

def status():
    with lock:
        result = {k: v for k, v in state.items() if k != "anchor"}
        result["time"] = current_time()
    result.update(duration=data["duration"], run_id=data["run_id"], algorithm=data["algorithm"])
    return result

PAGE = """<!doctype html><meta charset="utf-8"><title>Gemini × Colav Replay</title>
<style>body{background:#101e2c;color:#e4eef4;font:17px system-ui;margin:40px;max-width:1000px}h1{font-size:32px}button,select{padding:12px;margin:5px;background:#284152;color:white;border:1px solid #597281;border-radius:8px;cursor:pointer}button:first-child{background:#257a78}input{width:95%}pre{background:#172c3b;padding:20px;border-radius:10px;white-space:pre-wrap}.muted{color:#9ab0bd}img{max-width:100%}</style>
<h1>Gemini / Unity × Colav-Simulator</h1><p>原版 Gemini gRPC 位姿服务 · 已有 VO 追越记录 · PROTOTYPE</p>
<p class="muted">本页只控制回放。三维画面在 Unity 中运行；下方截图由 Unity 生成。</p>
<div><button onclick="cmd('play')">播放</button><button onclick="cmd('pause')">暂停</button><button onclick="cmd('reset')">回到起点</button>
<select id="rate" onchange="cmd('rate',this.value)"><option>1</option><option>4</option><option selected>8</option><option>16</option><option>32</option></select>倍
<button onclick="cmd('capture')">截取 Unity 画面</button></div>
<input id="seek" aria-label="回放时间" type="range" min="0" step="0.5" onchange="cmd('seek',this.value)">
<div id="chapters"></div><pre id="status">连接本地回放控制器…</pre><img id="shot" alt="Unity 截图（点击截图后出现）" style="display:none">
<p class="muted">L1 来源为 god 理想跟踪；无重新求解、无实船验证。波纹/船体外观为原型显示。</p>
<script>
const seekNode=document.getElementById('seek'), statusNode=document.getElementById('status'), shotNode=document.getElementById('shot');
async function cmd(a,v=''){await fetch('/control?action='+a+'&value='+encodeURIComponent(v))}
fetch('/data').then(r=>r.json()).then(d=>{seekNode.max=d.duration;for(const c of d.chapters){const b=document.createElement('button');b.textContent=c.label+' · '+c.time+'s';b.onclick=()=>cmd('seek',c.time);document.getElementById('chapters').appendChild(b)}});
setInterval(async()=>{const s=await (await fetch('/status')).json();if(document.activeElement!==seekNode)seekNode.value=s.time;statusNode.textContent=JSON.stringify(s,null,2)},500);
setInterval(async()=>{const r=await fetch('/screenshot',{method:'HEAD'});if(r.ok){shotNode.src='/screenshot?t='+Date.now();shotNode.style.display='block'}},2500);
</script>"""

class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200 if (outputs / "unity-replay.png").exists() else 404)
        self.end_headers()

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/control":
            q = parse_qs(url.query)
            action = q.get("action", [""])[0]
            value = q.get("value", ["0"])[0]
            with lock:
                state["time"] = current_time()
                state["anchor"] = time.monotonic()
                if action == "play":
                    if state["time"] >= data["duration"]: state["time"] = 0.0
                    state["playing"] = True
                elif action == "pause": state["playing"] = False
                elif action == "reset": state.update(time=0.0, playing=False)
                elif action == "seek": state.update(time=min(data["duration"], max(0.0, float(value))), playing=False)
                elif action == "rate": state["rate"] = min(32.0, max(0.25, float(value)))
                elif action == "capture": state["capture"] += 1
                state["revision"] += 1
            content, mime = json.dumps(status()).encode(), "application/json"
        elif url.path == "/status": content, mime = json.dumps(status()).encode(), "application/json"
        elif url.path == "/data":
            content = json.dumps({k: data[k] for k in ("run_id", "duration", "chapters")}).encode()
            mime = "application/json"
        elif url.path == "/readback":
            file = outputs / "pose-readback.json"
            content, mime = file.read_bytes() if file.exists() else b"{}", "application/json"
        elif url.path == "/screenshot":
            file = outputs / "unity-replay.png"
            if not file.exists(): self.send_error(404); return
            content, mime = file.read_bytes(), "image/png"
        else: content, mime = PAGE.encode(), "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, *_): pass

def pump():
    stub = rpc.SimulationStub(grpc.insecure_channel(args.address))
    last = None
    last_sent = 0.0
    while True:
        with lock:
            target, revision = current_time(), state["revision"]
        index = max(0, bisect.bisect_right(times, target) - 1)
        if (index, revision) == last and time.monotonic() - last_sent < 1.0:
            time.sleep(0.02)
            continue
        frame = frames[index]
        request = pb.StepRequest(time=frame["time"], stepSize=0.5,
            VesselPoses=[pb.Pose(north=p["north"], east=p["east"], heading=p["heading"]) for p in frame["poses"]])
        try:
            response = stub.DoStep(request, timeout=2)
            if not response.success: raise RuntimeError("Gemini rejected pose application")
            with lock:
                state.update(connected=True, error="", ack_time=frame["time"], sent=state["sent"]+1)
                if target >= data["duration"]:
                    state.update(playing=False, time=data["duration"])
            last = index, revision
            last_sent = time.monotonic()
        except (grpc.RpcError, RuntimeError) as exc:
            last = None
            with lock:
                state.update(connected=False, error=str(exc)[:220], playing=False,
                             time=target, anchor=time.monotonic())
            time.sleep(0.5)

threading.Thread(target=pump, daemon=True).start()
print(f"Gemini target: {args.address}; controls: http://127.0.0.1:{args.port}", flush=True)
ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
