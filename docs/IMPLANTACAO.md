# Vultr deployment and operating limits

## Current deployment

The 8 November 2026 pilot runs on a dedicated Vultr Shared CPU VM: 2 vCPUs, 2 GB RAM, 65 GB storage, Ubuntu 24.04 LTS. The selected instance quote was US$15/month, approximately US$0.022/hour, without automatic-backup or DDoS add-ons. The application uses Vultr Serverless Inference separately; the configured model is `qwen3.8-flash-next`.

The promotional credit was redeemed without adding a card. Account receipts, private credentials and support details stay outside the public source. This document is an architecture/operating record, not a statement of current remaining balance or a guarantee against provider charges.

## Trust boundaries

- **Public web layer:** HTTPS terminates at Caddy. Only the intended hostname is allowed. The controller is bound to `127.0.0.1:8765`, not exposed directly. The demo requires a separate application code; it is not the provider credential.
- **Controller:** an unprivileged `sheetkeeper` service holds server-only configuration. It validates requests, obtains a reviewable plan, starts a worker, verifies bounded JSON and records destruction. Keep private configuration outside the source package and screenshots.
- **Provider:** only the question, column names and row count are transmitted. Spreadsheet cells, worker output and stderr are not sent to the model in this version. Optional reasoning is disabled; output is JSON with a maximum of 2,500 completion tokens and a 25-second request timeout.
- **Worker:** rootless Docker, UID 10001, no network, read-only root, all capabilities dropped, no new privileges, private IPC, bounded temporary filesystems, 1 CPU, 256 MiB, 64 PIDs and code deadlines. No host directories, runtime sockets or service keys are mounted. It shares the host kernel; rootless is not a microVM boundary.

The controller-generated receipt reports the image ID and observed task outcome. The separate cloud audit passed eight fixed-code cases and three application lifecycles with no model calls. It checked actual kernel cgroup values inside the worker, memory/process behavior, cleanup and recovery; no orphan containers remained. Its network check observed loopback-only interfaces, without an external request. Docker's reported support and a configured flag alone would not establish these outcomes. The audit remains bounded, not an exhaustive security review.

## Reproduce the provisioning profile

Copy only selected public code to `/opt/sheetkeeper`, then follow [VULTR-PROVISIONING.md](VULTR-PROVISIONING.md). The bootstrap script is for a **new dedicated Ubuntu 24.04 VM**; review before running as root. It installs from Docker's official signed apt repository, masks rootful services, creates a service user without sudo/rootful-Docker access and installs a user-managed rootless daemon. It preserves AppArmor and does not weaken host sysctls.

Place actual values only in `/etc/sheetkeeper.env` (`root:sheetkeeper`, mode `0640`). Never copy this file into Git, frontend code, worker images, public evidence or presentation sources. The server reads process environment, not an automatically loaded repository `.env` file.

Required runtime settings include `SHEETKEEPER_REQUIRE_ROOTLESS=1`, the resolved worker image, an allowed hostname, a distinct access code, and the server-only inference key/model. `SHEETKEEPER_DEPLOYMENT_PROVIDER=vultr` labels the deployment as **server configuration**; it does not independently verify infrastructure.

## Usage controls

`SHEETKEEPER_INFERENCE_BUDGET_FILE` points to private persistent storage owned by the controller. `SHEETKEEPER_INFERENCE_MAX_CALLS` defaults to 10, configurable from 1 to 500. Each attempt is reserved under a file lock and persisted before network access; timeouts and errors consume an attempt. Corruption or invalid configuration blocks further calls. Restarting the controller does not reset this counter.

The live evaluation configuration uses 500 shared provider attempts, with three consumed by the recorded model-backed pilot. Evaluator access has been tested through the LabLab-link fragment flow in a fresh HTTPS tab; the page removes the fragment before API requests. The standalone URL accepts manual demo-code entry. The code gives access only to the bounded application, not SSH or the provider account. It is not included in public source.

This is a bounded request allowance, not a currency cap. Reconcile actual token/VM charges and promotional coverage before changing it. One model plan and one sandbox execution can be active at a time. The current prototype has no per-user quotas or tenant accounts; use synthetic inputs only and avoid exposing unrestricted model access.

The controller keeps up to 20 jobs in memory for one hour. Restarting it loses jobs/receipts still in memory, so export the final sanitized evidence before service changes. The worker is destroyed after each task; a cleanup failure blocks further execution until resolved. Record image/base digests and recheck them after rebuilds.

## Availability and cleanup

The promotion expires on **9 December 2026**. Evaluator access and the demonstration window are maintainer-controlled; no future cleanup has been claimed as complete. Delete billable VM/storage resources when that window ends, in time to avoid relying on expired credits. Stopping a VM does not necessarily stop billing. Disable or remove inference access when it is no longer needed, and verify the actual resource list and bill afterward.

The user authorized promotional credits only. Do not add a payment method, make a deposit, activate paid extras or spend personal money. Billing notifications are not enforcement limits. Credentials must remain private throughout final publishing and media export.

## Delivery status

The analysis/timeout/recovery pilot is recorded in [public-evidence](../public-evidence/README.md). The separate cloud boundary audit has completed and is published as a sanitized record. Evaluator access has been checked; source/deployment parity, media replacement and LabLab submission readback remain separate gates. Preserve the pre-event-origin disclosure and do not describe a draft, upload or configuration as an accepted competition entry.
