"""PROTOTYPE: export one existing Colav run; never rerun or invent dynamics."""
import base64
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

source = Path(sys.argv[1]).resolve()
output = Path(__file__).parent / "data"
output.mkdir(exist_ok=True)
manifest = json.loads((source / "manifest.json").read_text())
context = json.loads((source / "static_context.json").read_text())
episode = json.loads((source / "episode.json").read_text())
evaluation = json.loads((source / "evaluation.json").read_text())
frames = []
origin = None
for line in gzip.open(source / "decision/frames.jsonl.gz", "rt"):
    item = json.loads(line)
    ships = sorted(item["payload"].values(), key=lambda value: value["id"])
    if origin is None:
        origin = [ships[0]["state"][0], ships[0]["state"][1]]
    own = ships[0]
    balance = own.get("gnc_balance", {})
    vo = own.get("colav", {}).get("vo", {})
    poses = []
    for ship in ships:
        state = ship["state"]
        poses.append({"id": ship["id"], "north": state[0] - origin[0],
                      "east": state[1] - origin[1], "heading": math.degrees(state[2]) % 360,
                      "speed": ship["csog_state"][2]})
    frames.append({"time": item["sim_time"], "poses": poses,
                   "phase": vo.get("overtaking_state", "UNAVAILABLE"),
                   "mode": vo.get("execution_mode", "UNAVAILABLE"),
                   "rule": vo.get("driving_rule") or "NONE",
                   "roll_deg": balance.get("roll_deg"),
                   "environment": balance.get("environment", {}),
                   "actuators": [{k: p.get(k) for k in ("id", "actual_n", "angle_deg")}
                                 for p in balance.get("propulsion", [])]})
assert len(frames) > 1 and all(len(f["poses"]) == 2 for f in frames)
assert all(b["time"] > a["time"] for a, b in zip(frames, frames[1:]))
closest = min(frames, key=lambda f: math.hypot(f["poses"][0]["east"] - f["poses"][1]["east"],
                                             f["poses"][0]["north"] - f["poses"][1]["north"]))
chapters = [{"time": frames[0]["time"], "label": "起始状态"}]
for phase, label in [("COMMITTED", "追越承诺"), ("PASSED", "追越通过")]:
    hit = next((f for f in frames if f["phase"] == phase), None)
    if hit: chapters.append({"time": hit["time"], "label": label})
chapters.append({"time": closest["time"], "label": "最近接近"})
chapters.append({"time": frames[-1]["time"], "label": "记录结束"})
waypoints = episode["config"]["ship_list"][0]["waypoints"]
data = {"schema": "colav.gemini-replay-prototype.v1", "run_id": manifest["run_id"],
        "source_commit": manifest["code_commit"], "source_state": manifest["state"],
        "algorithm": manifest["executed_algorithm"], "tracker": manifest["executed_tracker"],
        "fallback_used": manifest["fallback_used"], "duration": frames[-1]["time"],
        "origin_north": origin[0], "origin_east": origin[1], "ships": context["ships"],
        "chart": {**context["enc"], "north": context["enc"]["origin_north_m"] - origin[0],
                  "east": context["enc"]["origin_east_m"] - origin[1]},
        "route": [{"north": n-origin[0], "east": e-origin[1]} for n,e in zip(*waypoints)],
        "chapters": sorted(chapters, key=lambda c:c["time"]), "frames": frames,
        "evaluation": {"status": evaluation.get("evaluation_status"),
                       "recorded_collision_count": evaluation.get("aggregate", {}).get("collision_count"),
                       "recorded_minimum_distance_m": evaluation.get("aggregate", {}).get("minimum_distance_m")},
        "limits": "Recorded simulation, not a new solver run. Tracker god is idealized L1. "
                  "Procedural hull; flat ENC chart; no Gemini EMR sensor validation. "
                  "Gemini Pose protocol applies N/E/heading only, not roll/heave/pitch."}
(output / "replay.json").write_text(json.dumps(data, separators=(",", ":"), allow_nan=False))
(output / "enc.png").write_bytes((source / "enc.png").read_bytes())
provenance = {"source_run": str(source), "files": {}}
for name in ["manifest.json", "episode.json", "static_context.json", "trajectory.parquet",
             "decision/frames.jsonl.gz", "enc.png", "evaluation.json"]:
    provenance["files"][name] = hashlib.sha256((source / name).read_bytes()).hexdigest()
(output / "provenance.json").write_text(json.dumps(provenance, indent=2))
print(json.dumps({"frames": len(frames), "duration": data["duration"], "chapters": data["chapters"]}))
