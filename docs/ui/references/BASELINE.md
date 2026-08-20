# UI Refactor Baseline

## Capture

- Captured: 2026-08-12, Asia/Shanghai.
- Worktree: `/Users/marine/Code/.worktrees/Colav-Simulator/mass-openbridge-ui`.
- Branch: `codex/mass-openbridge-ui`.
- HEAD: `783c5365d1ca373ac531fa99043469e00bf7e582`.
- Remote tracking branch: `marine/codex/mass-openbridge-ui`.
- Baseline UI image: `current-ui-baseline.png`.
- Source image dimensions: 2137 x 1300 RGBA PNG.
- Source image SHA-256: `2d1198511af961358c10cc5281700772987450f078304d83337cdb82804e0443`.

The image was supplied with the UI refactor handoff. It is preserved as the
pre-refactor visual reference; it is not a fresh browser capture from this
worktree.

## Local Services

| Port | State | PID | Process working directory |
|---|---|---:|---|
| 8010 | Listening | 25955 | `/Users/marine/Code/.worktrees/Colav-Simulator/mid-mpc-l1-l2-assembler` |
| 8011 | Listening | 93047 | `/Users/marine/Code/.worktrees/Colav-Simulator/unavailable-cards-8011` |
| 8012 | Free | - | Reserved for this UI worktree |

Port 8010 is not currently served from the main checkout. This audit did not
restart, stop, or alter either existing service. Before later browser QA, the
UI worktree must use port 8012 and its listener PID/cwd must be verified.

## Tooling

- Open Design MCP: enabled, local stdio transport.
- Selected future generation mode: Local Codex.
- CodeGraph: initialized in this worktree with version 1.0.1.
- CodeGraph index: 210 files, 3,925 nodes, 10,738 edges.
- CodeGraph pending changes after initialization: none.
- `.codegraph/codegraph.db` is machine-local; only `.codegraph/.gitignore` is
  eligible for version control.

## Verification

```text
node --check web_gui/app.js
PASS

/Users/marine/Code/Colav-Simulator/.venv/bin/pytest -q \
  tests/test_p1_capability_api.py \
  tests/test_p1_clock_enc_contract.py \
  tests/test_playback_speed.py
21 passed, 1 warning in 37.95s
```

The warning is an existing Starlette `TestClient` deprecation warning. No
production source was changed during baseline verification.
