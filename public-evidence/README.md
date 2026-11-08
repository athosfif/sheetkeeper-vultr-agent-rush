# Synthetic cloud execution records — 8 November 2026

These three JSON files are sanitized records from the real SheetKeeper web flow on its dedicated Vultr VM. They are **not** the historical Docker Desktop rehearsal and do not use the fixed-plan mode as a substitute for inference.

| File | What was run | Observed result |
| --- | --- | --- |
| [analysis-evidence.json](analysis-evidence.json) | Vultr-generated plan, then human-reviewed code in a disposable container | 6 rows; total 6,000; container destroyed; 655 ms sandbox interval |
| [containment-evidence.json](containment-evidence.json) | A new Vultr plan, then the application's explicit infinite-loop challenge | Timed out; exit -9; container destroyed; 3,433 ms sandbox interval |
| [recovery-evidence.json](recovery-evidence.json) | A fresh Vultr plan and analysis after the timeout | Same correct synthetic totals; container destroyed; 590 ms sandbox interval |

The challenge deliberately substitutes `while True: pass`; it is not presented as code the model decided to generate. Each receipt includes the code actually executed. Sandbox intervals include the controller's execution/cleanup path; they are not model latency or a measure of time saved in a business workflow.

Expected groups, independently checked against `fixtures/sales.csv`: **Busca 2,000; Social 1,500; Indicacao 2,500**. The three provider responses report `qwen3.8-flash-next`, 624 prompt tokens and 1,640 completion tokens in total (2,264 tokens). These fields do not independently attest model weights or hardware. No spreadsheet cell values were sent to the planner.

Copies use an explicit field allowlist. Account identifiers, support messages, credentials, the demo access code and private budget counters are excluded. `manifest.json` identifies these sanitized files by SHA-256. Hashes and controller-generated receipts establish what was recorded, not cryptographic third-party attestation or correctness for arbitrary spreadsheets.

The separate [cloud boundary audit](cloud-boundaries.json) completed on the same VM at 17:53 UTC: **8 cases and 3 additional application lifecycles**, all with fixed synthetic code and **zero model/API calls**. These are distinct from the three model-backed browser runs above; they must not be added together as extra inference calls. No orphan containers remained. The audit read the worker's kernel limits as `cpu.max=100000 100000`, `memory.max=268435456` and `pids.max=64`, and UID 10001. The network probe checked that the worker exposed only loopback; it did not send an external network request. The report includes actual timeout, memory-pressure, process-limit, excess-output, symlink-artifact and cleanup observations. It is a bounded audit, not an exhaustive security certification. The application supplies arithmetic/row-count checks; human semantic review remains necessary. In particular, these model outputs have only been validated on this small fixture, not on every malformed value or more than 24 groups.
