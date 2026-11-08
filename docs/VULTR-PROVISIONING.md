# New dedicated Vultr VM only

`scripts/provision_vultr.sh` is prepared for a **new Ubuntu 24.04 LTS VM with cgroup v2 and systemd**. This recipe was used for the dedicated 8 November 2026 pilot. A script remains an instruction set, not proof of isolation; see the separate sanitized runtime and execution records in `public-evidence`. Copy the selected public application source to `/opt/sheetkeeper` first, without private credentials, account receipts or media working files. Review before running as root:

```sh
SHEETKEEPER_NEW_VM=1 bash /opt/sheetkeeper/scripts/provision_vultr.sh
```

The script uses Docker's official signed apt repository and the packaged rootless extras. It masks system-wide Docker/socket/containerd units, creates an unprivileged `sheetkeeper` user outside `sudo` and `docker`, preserves Ubuntu's AppArmor settings, delegates CPU/memory/PID controllers to that user's systemd manager, and builds the sandbox image through its rootless daemon. The rootless socket stays local; no Docker TCP socket or sandbox port is published. Re-running preserves `/etc/sheetkeeper.env` and the persisted call counter. It can rebuild the worker image, so record the resolved image ID again after a rerun.

The controller runs under `sheetkeeper.service`, bound to `127.0.0.1:8765`. Inference starts **disabled**. `/etc/sheetkeeper.env` is `root:sheetkeeper 0640`; its contents belong only on the server and must never be printed, packaged or committed. `/var/lib/sheetkeeper` is private persistent storage for the attempt counter. After configuring the reviewed model, secret, allowed hostname and private access code, restart only the controller. The parent deployment process configures TLS and firewall separately; do not expose the controller before those gates pass.

Verify the real host: `docker info` must report rootless, cgroup v2, systemd and no resource warnings; verify actual memory/CPU/PID enforcement in a disposable container, then analysis, timeout containment, cleanup and recovery through the application. A successful script or model response does not prove those behaviors. Preserve the image ID, safe runtime metadata and observed costs. Rootless containers do not provide a VM boundary against a kernel vulnerability.

Official references checked 08 November 2026: [Docker apt installation](https://docs.docker.com/engine/install/ubuntu/), [rootless setup and prerequisites](https://docs.docker.com/engine/security/rootless/), [systemd and resource delegation](https://docs.docker.com/engine/security/rootless/tips/#limiting-resources), [Ubuntu AppArmor and rootless troubleshooting](https://docs.docker.com/engine/security/rootless/troubleshoot/). Docker documents that Ubuntu's packaged installation supplies the rootlesskit profile through AppArmor; this script does not disable AppArmor or alter sysctls.
