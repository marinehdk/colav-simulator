---
name: colav-decision-replay
description: Use when debugging Colav-Simulator behavior — why was target X primary, why a risk/AVOIDING transition, why the own ship was silent or routeless in the first seconds, why the planner turned/failed, tracker/AIS input quality, or comparing before/after a fix. Records ONE headless run with full per-tick decision evidence, then answers every per-tick decision question offline via probes (startup/primary/chain/solves/risk/explain/compare) instead of re-running the simulation. Trigger on "为什么/why primary", "开局/前N秒", "复盘/replay decisions", "避空气/phantom avoidance", Mid-MPC/AIS/VO debugging, or any request that would otherwise require re-running a scenario to inspect a decision.
---

# Colav Decision Replay: Record Once, Interrogate Offline

## Purpose

Answer per-tick decision questions for any Colav-Simulator run (VO / Fan-MPC / Mid-MPC, god/KF tracker, paper or historical-AIS scenarios) from a recorded evidence bundle — never by re-running the simulation.

Core discipline (inherited from the MASS-L3 colregs-probe pattern): **one recording, many probes**. A run is recorded once with full per-tick evidence; every subsequent "why" question is an offline read. If a probe cannot answer, the report says so with evidence gaps — it never guesses, and you never rerun to "look again".

## When to use

- "Why did the own ship show nothing / no route for the first N seconds?" → `startup`
- "Why is target X the primary?" / "为什么锁定 TS3" → `primary`
- "Why did risk go MONITOR → AVOIDING at t=7s?" → `risk` + `chain`
- "When did the planner first solve / why did it fail?" → `solves`
- "What did the planner see and do at tick t?" → `explain`
- "Did my fix change behavior?" → `compare`

## Workflow

### Step 1: Record once

```bash
cd /Users/marine/Code/Colav-Simulator
# Historical-AIS scene (deterministic; empty archive env unless the real archive is required):
COLAV_HAIS_ARCHIVE_PATH=.venv/bin/python -m colav_simulator.decision_replay record \
  --scenario hais_romsdal_20260701_120007_121007 \
  --algorithm mid_mpc_ipopt --tracker god --validation-rule-id multiship \
  --t-end 120
# Paper scenario:
.venv/bin/python -m colav_simulator.decision_replay record \
  --scenario head_on --algorithm vo --tracker god --validation-rule-id rule14 --t-end 60
```

- The trace lands in `runs/<run_id>/decision/` (`frames.jsonl.gz` + `events.jsonl` + `index.json`). The command prints `run_dir`; use it in every later step.
- `--t-end 120` is usually enough for a startup question; full voyages cost more Mid-MPC solves.
- Historical scenes need `COLAV_HAIS_ARCHIVE_PATH=/Users/marine/Downloads/浏览器下载/Hais_e716cfac-348c-417b-acbd-04a228732de7.zip` for the real archive; with the env unset the catalog is deterministic and small.
- Failed runs still produce a truncated-but-readable trace (that is when you most need it).

### Step 2: Interrogate offline (each is one command, JSON out)

```bash
RUN=runs/<run_id>
.venv/bin/python -m colav_simulator.decision_replay summary  $RUN            # what is in the bundle
.venv/bin/python -m colav_simulator.decision_replay startup  $RUN --seconds 30
.venv/bin/python -m colav_simulator.decision_replay primary  $RUN --at 7
.venv/bin/python -m colav_simulator.decision_replay chain    $RUN 3 --t0 0 --t1 30   # target_id=3
.venv/bin/python -m colav_simulator.decision_replay solves   $RUN
.venv/bin/python -m colav_simulator.decision_replay risk     $RUN [--target-id 3]
.venv/bin/python -m colav_simulator.decision_replay explain  $RUN 7.0
.venv/bin/python -m colav_simulator.decision_replay compare  $RUN_A $RUN_B
```

Python equivalent (pytest, custom questions):

```python
from colav_simulator.decision_replay import TraceBundle, probes, signals
bundle = TraceBundle("runs/<run_id>")
report = probes.why_primary(bundle, at=7.0)
frame = bundle.frame(bundle.seq_at_time(7.0))          # raw payload, byte-equal to GUI telemetry
signals.threat_document(signals.ship_of(frame))        # full schedule/vectors when probes are not enough
```

### Step 3: Attribute before fixing

Read probes in causal order and stop at the first layer that contradicts expectation:

1. `control_source` (startup rows): `HISTORICAL_REFERENCE` means the own ship is factual playback — the planner is **supposed** to be silent; route/planned-route absence before the first control transfer is by design, not an AIS data gap.
2. `risk`/`chain`: tracker health (`observation_health`, NIS, AIS state) → physical facts (range/DCPA/TCPA) → display class → lifecycle (encounter/role/risk). A wrong decision with healthy inputs is a threat/lifecycle defect; a wrong decision with degraded inputs is a tracking defect.
3. `primary`: schedule entries carry `context` + `priority_reason`; the `primary_switch_history` gives the exact switch events.
4. `solves`: first solve, feasibility, `failure_code`, selected vs applied reference.
5. Only after the layer is pinpointed, read that module's source and change code. Then `record` the same spec again and `compare` — regress the cohort, not just the scenario.

## Report shapes (abbreviated)

```json
// startup
{"first_control_transfer": 7.0, "first_planner_solve": {"t": 7.0, "solve_id": 1},
 "rows": [{"seq": 1, "t": 0.0, "control_source": "HISTORICAL_REFERENCE", "planner": null,
           "primary": null, "applied": {"course_rad": 5.13, "speed_mps": 6.3}}], "events": [...]}
// primary
{"at": 7.0, "primary": {"target_id": 3, "generation": 1},
 "schedule_entries": [{"key": [3, 1], "context": "CURRENT_PRIMARY", "priority_reason": "...",
                       "vector": {"dcpa_m": 1881.7, "tcpa_s": 219.7, "range_m": 2355.0,
                                  "display_class": "MONITOR", "lifecycle_risk": "ACTIVE"}}],
 "primary_switch_history": [...]}
```

## Pitfalls

- **Frame sequence is 1-based** (`bundle.frame(1)` is the first tick); `seq_at_time` returns 0 only when the trace is empty.
- Legacy run dirs (no `decision/`) are `reduced`: only `events.jsonl` is available; frame probes return empty — re-record instead of guessing.
- The GUI console script always loads the **main checkout** (worktree footgun): record from the checkout you are debugging. Use `.venv/bin/python -m colav_simulator.decision_replay` in worktrees.
- Keep `COLAV_HAIS_ARCHIVE_PATH=` empty for reproducible offline work; set it only when the specific archived scene is the subject.
- Parquet is banned in-process (SIGSEGV); the trace is JSONL+gzip on purpose — do not "upgrade" it.
- `predicted_trajectory` / `target_predictions` are deliberately excluded from probe briefs to keep reports small; pull them from the raw frame when needed.
