# M2-F build log — demo packaging (spec #79 §5 M2)

- Build output renamed to the plan's acceptance path: `Builds/sango.app`
  (was `Builds/M1-Standalone.app`; one-line change in
  M1VerifyCapture.BuildStandalonePlayer, Mono backend unchanged).
- Build: exit 0, 184 MB.
- Double-click acceptance: `open sango/Builds/sango.app` (the plan's own
  command) → four-view demo opens: bridge view with weather panel,
  Simulation panel (RT rotating preview), Autonomous Control, radar disc
  with liner blip; fishing boat + liner + archipelago in frame.
  Evidence: `m2f-sango-app-demo.jpg`.
- fps record (demo conditions, M2 closeout): 76–120 fps across sessions
  (editor Game view 84.7–162.5 depending on overlays/night; standalone
  player smokes 76.6–120.0), all ≥2× the ≥30 fps gate. M0 anchor was
  109 fps @1738×1032; no material regression from M2's ships/overlays.
- Encounter demo remains available as `Builds/M2E-Standalone.app`
  (encounter scene with the three COLREG patterns, keyboard-driven).
- Verdict: M2 acceptance letter satisfied — four views ✓, demo build
  double-clickable ✓, fps recorded ✓.
