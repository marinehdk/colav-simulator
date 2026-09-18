# Full Stack Mid-MPC: T270 inline capacity and full-run follow-up

## Reported failure

Run `7bcc064f-f5d7-4072-b219-fed352a74018` failed at T270 with `INLINE_CAPACITY_EXCEEDED: Tier0 and mandatory failures exceed capacity`. The exact saved specification reproduces it in `e9686d07-1a2c-4449-a9e6-dc10a6a8de75`.

The captured semantic record was **accepted=true, with no mandatory failures**. Its normal inline projection is 1,008 bytes; its smallest legal summary is approximately 468 bytes. `EvidenceEnvelope.to_inline_dict` externalized the receipt's large prediction only when fewer than 256 bytes remained. When remaining space was above that floor but below the actual verdict size, serialization raised and aborted execution. This was not a rejected safety verdict.

The envelope now attempts to fit the actual verdict, then uses the existing typed external-artifact reference for the full accepted prediction and retries once. It retains every mandatory failure, accepted/rejected status, identity hash and artifact reference, never changes the source receipt, and still rejects an envelope that genuinely cannot fit. Tests cover both accepted and rejected verdicts in the previous blind interval.

## Additional issue exposed by full-length validation

After the inline fix, full validation reached T700 and found an infeasible charted crossing problem. The NLP forced astern-passing geometry even when the candidate was still approaching the target at the end of its finite horizon. The independent L4 gate already requires passing geometry only when CPA occurs before the last horizon knot. This mismatch excluded a safe deferred-passing/braking candidate.

COLAV_STRICT now uses the same finite-horizon CPA criterion as L4. CPA clearance and chart hard rows stay active, actual within-horizon crossing-bow candidates remain rejected, and lifecycle duty/release is untouched. MASS_PARITY remains unchanged.

Cold-start repair also explores deceleration under the existing speed/rate bounds for charted problems. Retained/timed routes or COLREG course commitments prioritize that option because turn space is constrained; ordinary unretained chart routes retain their original turning-first search and only then try braking. An early braking-first variant regressed ordinary island progress and was discarded; the final island regressions pass.

The frozen T700 case changed from IPOPT `Infeasible_Problem_Detected`, 90 iterations and 43.46 m maximum row violation to an actual IPOPT feasible iterate with **zero constraint violation and zero slack**, without changing constraint thresholds. Its regression fixture retains the original chart and all targets. The full closed loop continues through the unchanged independent L4 acceptance path.

## Full original-configuration run

Final Run `f401ee4b-a27f-4c64-b560-80fe1327c344`, generated through WebSessionManager with the user's exact Full Stack specification (only artifact output directory changed):

- FINISHED at **1800.1 s**, no runtime failure.
- **18,001 recorded frames**, through T1800.0, chart replay READY and untruncated.
- Recorded event stream includes `time_limit` and `session_finished`, with no collision/grounding/fallback event.
- The original configured scenario ends at 1800 s. This is time-limit completion, **not arrival**: the last recorded position remains **1024.72 m from the mission endpoint**. Do not label this as arrival qualification or silently extend the user's duration.

The earlier 183-second check was insufficient to establish whole-scenario reliability. This verification explicitly ran the entire configured interval. Independent evaluator outcome and final deployment are recorded below.

## Regression scope

The test suites cover bounded evidence transport, strict numerical rows, genuine crossing-bow rejection, outside-horizon CPA, the real T700 chart, island/reef obstacles, frozen MASS parity, native-GNC numerical/performance fixtures, adapter scheduling and both route bridges. Existing solver lint warnings for `solve` complexity, one unrelated long line and an unrelated return-count limit were reproduced on the pre-change file; no broad formatting/refactoring was performed.

## Final validation and deployment

- **214 focused tests passed** in one consolidated final run (90.96 s).
- Same independent evaluator/profile: **COMPLETE / hard gate PASS**. Global and ownship physical collision/grounding counts are all zero; minimum ownship hull clearance **231.63447 m** (required 50 m). No fallback. COLREG quality scores remain separate from hard safety; this is not blanket COLREG or arrival qualification.
- The usual post-run exporter retained approximately 3.97 GB on the user's 8 GB Mac while repeatedly decoding full diagnostic records and building trajectory hashes. Verification PID **83900** was terminated only after confirming the complete Parquet footer and **72,004 vessel rows** were persisted. This did not interrupt the already FINISHED simulation, sealed READY replay, or 8010.
- Independent assessment was completed with a bounded physical-column extraction instead: the original Evaluator consumes the same planar positions, heading/surge, times and hull dimensions as `session.vessel_data`. Episode/ENC hashes were matched against a fresh preparation. Missing absolute UTC/solver-diagnostic fields were not invented; they are not inputs to these physical hard gates. Peak memory **452,739,072 bytes**. The standard full diagnostic/hash export was not claimed complete.
- 8010 restarted with the fixes; original configuration restored as CREATED session `fd6443e8-caa6-401b-ade2-b5437482f226`. No duration, acceptance threshold or safety margin was changed.

Raw run data remain in `tmp/full_stack_270s_20260918/runs/f401ee4b-a27f-4c64-b560-80fe1327c344`. Independent evaluation is preserved in this report's evidence directory. The separate `mempalace mine` process (PID 58547) was not part of simulation verification and was not stopped without user authorization.
