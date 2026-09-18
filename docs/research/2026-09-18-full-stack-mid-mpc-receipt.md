# Mid-MPC + Full Stack failure at 30 seconds

## Diagnosis

User Run `1346c34e-c981-4ca5-b208-b2adc5496c11`: Three-Ship, Mid-MPC, God tracker, modular FCB45 Full Stack, 10-second planner period, requested 5×. The backend is FAILED, not hung; measured speed before failure was 5.01×.

At T=30 s the new candidate revision was rejected for `RECOVERY_TIME_CHANGED`. The previous accepted plan passed the existing continuation checks (`ROLLING_PLAN_CONTINUATION`, checked at 30, valid through 40). However the integration cached its accepted receipt only inside `if execution_route is not None`. Original GNC emits that packet; modular Full Stack does not. Consequently the rejection exception supplied `accepted_plan_receipt=None`, overwriting the held solution's valid receipt in the adapter trace. The route bridge correctly rejected missing authority.

## Fix and boundaries

Cache every newly accepted canonical receipt, independent of whether a native execution-route packet is emitted. Keep the native packet cache conditional. No acceptance criterion, safety gate, receipt identity/expiry, planner cadence, or solver policy changed. A genuinely unaccepted plan still cannot become an executable route.

## Verification

- Exact saved RunSpec reproduced the original failure at 30.0 s in Run `f74c38db-8251-4abe-8dd8-e570e26a3bbc`.
- The same feedback loop passes through 60.0 s after the fix, Run `7f7e5df7-cb54-4fcb-8529-8266ef86d011`.
- All vessel states in the 300 pre-failure frames compare exactly equal before/after.
- New real Mid-MPC acceptance test fails before the fix (`_last_plan_receipt=None` despite an issued receipt) and passes after.
- New test plus scheduler, modular route wiring, native route geometry and integration tests: **62 passed**. Ruff and diff checks pass.
- An existing audit test that changes the mission route expects continuation even though current validation rejects it; it failed before this fix and was left unchanged. It is not part of the passing focused result above.

## Deployment and extended run

8010 was restarted after verifying the original session was FAILED. The same exact saved Full Stack configuration was recreated as Run `8d130470-a021-4510-a7e1-06f368971c99` and exercised through the production HTTP/session scheduler. It passed T=30 s and reached **183.1 s**, then was deliberately paused for inspection/resumption, with no failure. Requested rate was set to 5× after initial startup; at T=119.4 s the backend measured **5.00274×**, no realtime limit. The complete samples and restored specification are in `evidence/full-stack-receipt-20260918/live-check.json`.

This validates the reported receipt-loss failure and subsequent repeated decision boundaries. It is not a new full-scenario safety or arrival qualification for the modular Full Stack plant.
