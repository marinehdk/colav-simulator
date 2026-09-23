# VO + original GNC, ten-target Romsdal scene

## Reproduction

Run `9d6fb77d-82ef-4d2b-baa0-8ba53e3269b6` used the shipped `romsdal_busy_water_16` scene (Ship0 plus ten targets), seed 0, God tracker, behavior-compatible VO, `original-gnc-20260914-v1-env-on`, 0.1 s integration, 1 s VO solves, 182 m hard and 190 m preferred hull clearance, and strict no fallback. The paused frame at 116.1 s matches the reported screenshot.

The run manifest labels this scenario G2 and the selected VO capability profile G3. The evidence below qualifies this exact demonstration run; it does not claim a general G3 multiship proof or numerical reproduction of the 2011 paper.

The decision trace shows that the large heading was a real command and response:

| Time | Actual heading | VO heading | Relevant state |
| --- | ---: | ---: | --- |
| 0 s | 0° | 36.6° | TS2 crossing give-way |
| 11 s | about 2° | 90° | Starboard command has grown while GNC is still turning |
| 77 s | 73.4° | 126.6° | Give-way commitment has no feasible forward cell; emergency relaxation |
| 116 s | 119.8° | 126.6° | TS3 crossing and TS4 head-on remain active |
| 117–172 s | varied | zero speed | Only the 128 zero-speed heading cells remain feasible |

The baseline reached the goal at 844.3 s with no collision, grounding, or fallback. It nevertheless commanded zero speed for 55 s, spun through 179.4° actual heading, and reached 16.7°/s actual yaw rate after propulsion resumed. Safety completion alone was insufficient for the demonstration. The evaluator's conservative Ship0–TS2 hull-clearance lower bound was 180.23 m; this is below the planner's configured 182 m hard margin, even though the evaluator's 50 m hard gate passed.

## Cause and correction

During give-way commitment, `_compute_optimal_controls` replaced the mission velocity reference with a vector along the previous selected heading. Successive solves then preferred progressively larger starboard headings and let speed rise while the slow original GNC was still turning. At 77 s, the remaining constrained cells were exhausted, and emergency relaxation selected 126.6°.

After that turn, `_apply_give_way_commitment` imposed two incompatible demands for an active head-on lock: heading at least as large as the previous 126.6° command, and positive forward progress relative to the encounter-entry course. The latter requires a heading inside the forward 90° half-plane. The stop row was exempt from both restrictions, so it became the only available row from 117 to 172 s.

The correction keeps the mission velocity as the cost reference when several targets are tracked during crossing/head-on commitment, while retaining the established course reference for a single target. It also allows a safe reduction of a previous head-on turn while remaining starboard of the entry course. The single-target crossing regression requires its original stable turn; the multi-target policy avoids the command ratchet. Dynamic hull-clearance, VO, COLREG, and backend envelope masks still govern every candidate. No scenario-specific planner branch or clearance relaxation was added.

## Short replay evidence

Run `3a41e17a-74ca-497c-99c7-df0f328c58fa` used the same scene, seed, algorithm, GNC, and safety settings, ending at 220 s for the encounter probe. The maximum actual heading was 47.09°, maximum commanded heading 47.81°, maximum actual yaw rate 1.25°/s, and zero-speed command duration 0 s. No Ship0 collision or grounding occurred; minimum conservative Ship0–target hull-clearance lower bound was 206.14 m. This probe validates the first encounter but does not establish mission completion.

## Full-run acceptance

Final-code run `fee7d16d-e1e0-4571-bc39-2f88f5fe08d4` used the unchanged 1200 s scene limit. Ship0 triggered `goal_reached` at 823.1 s. The manifest records `FINISHED/COMPLETED`, VO executed, no fallback, and no failure. All 824 actual VO solves reported `SUCCESS`. The completed evaluator passed collision, hull-clearance, grounding, fallback, and run-completion gates. Global all-vessel collision and grounding counts were zero.

The maximum actual heading from the northbound mission course was 47.09°, maximum selected heading 75.94°, maximum actual yaw rate 1.39°/s, and zero-speed command duration 0 s. The minimum conservative Ship0–target hull-clearance lower bound was 195.46 m, above the configured 182 m planner margin. Target-by-target minimums:

| Target | Minimum center distance | Conservative hull clearance lower bound |
| --- | ---: | ---: |
| TS1 | 381.9 m | 353.1 m |
| TS2 | 234.9 m | 206.1 m |
| TS3 | 257.2 m | 228.4 m |
| TS4 | 296.1 m | 267.4 m |
| TS5 | 912.9 m | 884.2 m |
| TS6 | 1439.8 m | 1411.1 m |
| TS7 | 224.2 m | 195.5 m |
| TS8 | 301.3 m | 272.6 m |
| TS9 | 758.0 m | 729.3 m |
| TS10 | 293.7 m | 264.9 m |

After the last close approach, Ship0's eastward route offset fell from 283.4 m at 700 s to 152.5 m at goal arrival, while heading port toward the mission line. The evaluator's formal return-voyage window begins at 933 s, after goal termination, so its return-voyage sample count is zero. This run shows route convergence and goal arrival, but has no post-goal route-crossing evidence.

The full replay had at least two tracked targets in every active give-way solve. Thus the final multi-target cost-reference branch was exercised throughout those solves; the single-target policy is separately covered by its closed-loop crossing regression.
