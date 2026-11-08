# SheetKeeper — a result you can check

**FIGUEIRA AI · Vultr Agent Rush · C1: Blast Radius Zero**

SheetKeeper turns a spreadsheet question into a reviewable plan, runs the approved Python code in a disposable sandbox, and returns a chart with an execution receipt. It is designed for a small team that needs to explain where a number came from, rather than copy an unverified answer out of a chat.

**Demo:** https://sheetkeeper.64-177-50-57.sslip.io/  
**Repository:** https://github.com/athosfif/sheetkeeper-vultr-agent-rush

The HTTPS application is deployed on a dedicated Vultr VM. The LabLab application link provides scoped evaluation access through a demo-code fragment; the page removes that fragment before making API requests. The standalone URL also supports manual code entry. This demonstration code grants no SSH or provider-account access and is intentionally absent from this repository. Source publication, evaluator access and final LabLab submission are separate steps. This README documents the actual cloud run and remaining delivery gates, not submission acceptance or eligibility approval.

## Try the workflow

1. Enter the demo code supplied by the maintainer. Use **synthetic data only**.
2. Choose **Use synthetic sample**, then change Preparation mode to **Vultr**.
3. Choose **Prepare plan**. Read the summary and open **Inspect code**.
4. Choose **Run analysis** after reviewing the code. Check the chart and download the execution receipt.
5. Prepare another plan and choose **Test containment**. This explicit challenge runs a three-second infinite loop; the application stops it and destroys its worker.
6. Prepare and run a fresh task to demonstrate recovery.

The fixed local rehearsal mode is clearly labeled **no AI**. It is not the mode used for the cloud inference records below. Editing the question, CSV or provider invalidates the old plan before another run.

## What was demonstrated on Vultr

On **8 November 2026**, the real browser flow called Vultr Serverless Inference using `qwen3.8-flash-next`. The returned identifier matched the request. A human reviewed the generated code before execution.

| Run | Observed output | Sandbox execution/cleanup interval |
| --- | --- | --- |
| Analysis | 6 rows; total **6,000**; Busca 2,000, Social 1,500, Indicacao 2,500; worker destroyed | 655 ms |
| Deliberate containment challenge | Infinite loop timed out; exit -9; worker destroyed | 3,433 ms |
| Fresh analysis after containment | Same correct fixture result; worker destroyed | 590 ms |

[Sanitized execution records](public-evidence/README.md) include executed code, input/code hashes, results, limits, cleanup state and provider-reported token usage. They are distinct from the October local rehearsal. The three model responses report **2,264 tokens** in total; the intervals above exclude model planning and are not business time-saving measurements.

The challenge is an application-controlled test, not a claim that the model autonomously attempted unsafe behavior. Model identifiers and controller receipts are reported evidence, not independent attestation of model weights or hardware. The separate [cloud boundary audit](public-evidence/cloud-boundaries.json) also passed **8 cases and 3 fixed-fixture application lifecycles**, without additional inference calls. It independently checked worker removal and found zero orphan containers. Inside the worker, the kernel reported 1 CPU (`cpu.max=100000 100000`), 256 MiB (`memory.max=268435456`), 64 PIDs and UID 10001. It also exercised memory/process limits, timeout, output bounds, symlink-artifact rejection, read-only/host/secret boundaries and recovery. Network isolation was checked by observing only a loopback interface; the audit did not send external traffic.

## How Vultr powers the application

```text
Browser —HTTPS→ Caddy on the Vultr VM
                       │
                SheetKeeper controller (unprivileged, loopback only)
                       ├── metadata-only plan request → Vultr Serverless Inference
                       └── reviewed code + CSV → rootless Docker worker
                                                  │
                                          bounded JSON result
                                                  │
                                      verify → destroy → receipt
```

The dedicated VM uses Ubuntu 24.04 LTS, 2 shared vCPUs, 2 GB RAM and 65 GB storage. The observed Docker runtime was 29.9.3 with **rootless**, **cgroup v2** and the **systemd** cgroup driver. The worker image ID is retained in each receipt; the Python base is pinned by digest in `sandbox/Dockerfile`.

The controller holds the inference key and sends **only the question, column names and row count** to the model. Spreadsheet cell values stay on the VM and enter the worker as input. The model returns JSON containing a summary and code; the controller does not execute that code in its own process.

Each worker runs as UID 10001 with no network, a read-only root filesystem, dropped capabilities, no new privileges, bounded writable temporary filesystems, **1 CPU, 256 MiB and 64 PIDs**. No host directory, Docker socket or service key is mounted into the worker. Ordinary jobs have a 15-second code deadline; the deliberate containment challenge uses 3 seconds. Rootless containers reduce privileges but are not a separate kernel/VM security boundary.

## Run locally without provider calls

Requires Python 3.12+; the application uses the Python standard library. From the repository root:

```sh
PYTHONPATH=src python3 -m sheetkeeper.server --port 8767
```

Open `http://127.0.0.1:8767`. The default fixture mode prepares a fixed sample plan and makes no model call. To execute that plan, provide a Linux Docker daemon and build the sandbox image:

```sh
docker build -t sheetkeeper-sandbox:prep sandbox
```

There is **no fallback to running generated code on the host**. With Docker unavailable, planning remains inspectable and execution is blocked. The historical `scripts/check_docker.py` writes the October local-rehearsal report; use it only in that context, not as proof of a new cloud run.

## Configure a dedicated deployment

See [provisioning](docs/VULTR-PROVISIONING.md), [deployment and operating limits](docs/IMPLANTACAO.md) and [current verification status](docs/VULTR-EXECUTION-PLAN.md). The controller reads process environment variables; it does not automatically load `.env`. `.env.example` contains names and non-secret defaults only.

Inference is disabled by default. Enable it only on the server with a reviewed model, private provider key, allowed hostname and access code. Keep the key outside Git, frontend code, worker images, logs and public receipts. The provider request has a 25-second timeout and a 2,500-token output limit, requires JSON output and disables optional reasoning. Results are not sent back for automatic repair in this version.

A persistent attempt counter reserves a slot **before** the provider request; failures and timeouts count. The pilot used a 10-call ceiling. The deployed evaluation ceiling is **500 shared provider attempts**, with three consumed by the recorded model-backed pilot. The configurable range is 1 to 500; this is a shared demo budget, not a per-user quota. Invalid or corrupted counter state blocks calls. It is a request ceiling, not a dollar meter or a substitute for cloud billing reconciliation.

## Verification and limits

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
node tests/test-ui-state.cjs
```

The current local suite passed **30 Python tests** and the UI state regression test. It covers input/output contracts, provider-envelope handling, access/origin checks, stale-plan invalidation, bounded capture, cleanup state, persisted call limits, concurrent reservations and restart behavior. Mocked tests are separate from the three real Vultr application runs. The separate cloud audit used fixed synthetic probes and is reported independently; it did not make additional model calls.

One task executes at a time; up to 20 jobs remain in memory for one hour. Restarting the controller discards job records, but not the persistent call counter. CSV input is limited to 200 KB, 2,000 rows and 24 columns; the result contract supports at most 24 groups. The chart derives from the returned JSON.

Row counts and group sums are checked, but semantic correctness still requires human review. The recorded model outputs were checked against one six-row synthetic fixture; they are not validated for every invalid value or a larger number of groups. The prototype does not provide account-based tenancy, production compliance, clinical decision-making or a measured operational saving. Use no personal, medical or confidential data in this demo.

The promo credit expires on **9 December 2026**. Evaluator access was checked in a fresh browser tab over valid HTTPS. Ongoing demo availability and promotional-credit use require maintainer management; no uptime beyond the promotion is promised. A stopped VM can still incur charges; delete billable resources when the authorized demonstration window ends, before relying on credit expiry. A billing alert is not a spending cap.

## Origin and competition disclosure

The initial SheetKeeper core was prepared on **1 October 2026**, before this event's online build window. The 6–8 November work added/revised UI state handling, persistent provider limits, Vultr provisioning, real inference and the cloud analysis/containment/recovery evidence. The pre-event baseline is preserved separately; [the earlier Portuguese README](docs/README-PREPARATION-20261106-PT.md) is retained as historical context.

The eligibility of reusing that baseline has **not** been confirmed by the organizers. This disclosure and the cloud work do not imply eligibility, judging acceptance or an award. The selected source is MIT-licensed; see [LICENSE](LICENSE).
