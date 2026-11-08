# Cloud verification status — 8 November 2026

## Completed and recorded

- The official event credit was redeemed. This repository deliberately excludes private billing/account evidence.
- The dedicated Vultr VM runs Ubuntu 24.04 LTS and serves the application over HTTPS through Caddy. The Python controller remains on loopback under an unprivileged service account.
- Docker reported rootless, cgroup v2, systemd and no resource warnings. The sandbox image ID is recorded in each execution receipt. Runtime declarations are distinct from tests that exercise each boundary.
- Three real application flows were completed through the browser: metadata-only Vultr inference → review → analysis; explicit timeout containment; a fresh analysis after containment.
- Both analyses independently matched the six-row fixture: total 6,000; Busca 2,000, Social 1,500, Indicacao 2,500. All three receipts report worker destruction. The timeout receipt records `timed_out: true`, exit -9 and a 3,433 ms execution/cleanup interval.
- The three provider responses report `qwen3.8-flash-next`, 624 prompt tokens and 1,640 completion tokens. These metadata do not independently attest the serving model weights or hardware.
- A separate cloud audit completed at 17:53 UTC with 8 cases and 3 fixed-fixture application lifecycles, zero provider calls, verified worker removal and zero orphan containers. The worker read back cgroup limits of 1 CPU, 268,435,456 memory bytes and 64 PIDs, UID 10001 and only the loopback interface. No external egress request was sent by that network probe. See the sanitized `public-evidence/cloud-boundaries.json`.
- A fresh browser tab validated the evaluator-link flow over valid HTTPS: the demo fragment populated its separate access field and was removed from the visible URL before API requests. The server reported the real rootless runtime. The deployed shared evaluation ceiling is 500 persisted provider attempts; the three recorded model-backed runs consumed three.
- Local validation passed 30 Python tests and the UI state regression test. These are not counted as cloud execution cases.

The public, sanitized records are in [`public-evidence`](../public-evidence/README.md). Private access credentials, account information and support conversations are excluded.

## Remaining gates before final delivery

1. Preserve the completed audit and pilot records. Re-run affected checks if runtime, code, container image or isolation settings change; a past pass does not prove a changed release.
2. Preserve the validated evaluator-link flow on the final release. Keep the live code out of public source, logs and screenshots; publish it only in the intended LabLab application link. A future configuration change requires a new fresh-tab check.
3. Check language switching, mobile layout, request limits, authentication and the current persisted call budget on the final deployed source. Recheck affected behavior after a material code/configuration change.
4. Reconcile provider/VM consumption with the promotional balance. Call counts and token counts do not prove the account bill. Keep all usage within the authorized credits; add no card, deposit, paid plan or own-money funding.
5. Replace pending-access narration and presentation states with the observed cloud results. Preserve original media; label edited captures and the deliberate containment challenge.
6. Publish the reviewed source and verify the public repository, license, setup instructions, demo URL and selected artifacts. Check that the public commit and deployment match this source before final LabLab delivery.
7. Verify the current official event deadline and submission fields. Complete the required LabLab entry and read back its actual saved/submitted state. Do not infer submission from file selection, an editor step or a complete-looking draft.
8. Disclose the 1 October pre-event core. Reuse eligibility remains unconfirmed until an organizer says otherwise.
9. Arrange resource deletion at the end of the authorized demo window, before the 9 December credit expiry. A stopped instance can remain billable. Confirm resources and balance after deletion; do not claim future cleanup has already happened.

## What the pilot does and does not prove

The live runs establish that this specific synthetic request traveled through the real provider/controller/worker path and returned the expected fixture result, with a containment/recovery sequence recorded. They do not establish arbitrary spreadsheet correctness, an exhaustive adversarial security review, independent model/hardware attestation, production readiness, time saved by a real business or eligibility for judging.

The October Docker Desktop rehearsal and the 6 November local UI review remain historical records, distinct from this cloud pilot. Preserve their dates and environment labels.
