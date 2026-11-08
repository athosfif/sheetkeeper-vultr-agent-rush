#!/usr/bin/env bash
# Run as root ONLY on the new, dedicated SheetKeeper Ubuntu 24.04 VM.
set -euo pipefail
umask 077
[[ ${SHEETKEEPER_NEW_VM:-} == 1 && $(id -u) == 0 ]] || { echo 'Require root and SHEETKEEPER_NEW_VM=1'; exit 1; }
. /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 24.04 && -f /sys/fs/cgroup/cgroup.controllers ]] || exit 1
[[ -f /opt/sheetkeeper/src/sheetkeeper/server.py && -f /opt/sheetkeeper/sandbox/Dockerfile ]] || exit 1
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y ca-certificates curl uidmap dbus-user-session slirp4netns apparmor python3
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod 0644 /etc/apt/keyrings/docker.asc
cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
# Block package post-install hooks from starting a rootful daemon.
systemctl mask docker.service docker.socket containerd.service
systemctl stop docker.service docker.socket containerd.service 2>/dev/null || true
apt-get update -qq
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-ce-rootless-extras
id sheetkeeper >/dev/null 2>&1 || useradd --create-home --user-group --shell /bin/bash sheetkeeper
[[ ! $(id -nG sheetkeeper) =~ (sudo|docker) ]] || { echo 'Service user must not have sudo/rootful Docker access'; exit 1; }
for subfile in /etc/subuid /etc/subgid; do
  awk -F: '$1=="sheetkeeper" && $3>=65536 {ok=1} END {exit !ok}' "$subfile" || { echo "Missing subordinate range: $subfile"; exit 1; }
done
sk_uid=$(id -u sheetkeeper)
install -d -m 0755 "/etc/systemd/system/user@${sk_uid}.service.d"
cat > "/etc/systemd/system/user@${sk_uid}.service.d/delegate.conf" <<EOF
[Service]
Delegate=cpu cpuset io memory pids
EOF
systemctl daemon-reload
loginctl enable-linger sheetkeeper
systemctl start "user@${sk_uid}.service"
as_user() { runuser -u sheetkeeper -- env XDG_RUNTIME_DIR="/run/user/$sk_uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$sk_uid/bus" DOCKER_HOST="unix:///run/user/$sk_uid/docker.sock" "$@"; }
# Ubuntu's packaged rootlesskit AppArmor profile is retained; no sysctl changes.
[[ ! -f /etc/apparmor.d/rootlesskit ]] || apparmor_parser -r /etc/apparmor.d/rootlesskit
if [[ ! -f /home/sheetkeeper/.config/systemd/user/docker.service ]]; then
  as_user dockerd-rootless-setuptool.sh install
fi
as_user systemctl --user enable --now docker.service
for controller in cpu memory pids; do
  grep -qw "$controller" "/sys/fs/cgroup/user.slice/user-${sk_uid}.slice/user@${sk_uid}.service/cgroup.controllers"
done
as_user docker info --format '{{json .}}' | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["CgroupVersion"]=="2" and d["CgroupDriver"]=="systemd"; assert any("rootless" in x for x in d["SecurityOptions"]); assert not d.get("Warnings"),d.get("Warnings")'
chown -R root:root /opt/sheetkeeper
find /opt/sheetkeeper -type d -exec chmod 0755 {} +
find /opt/sheetkeeper -type f -exec chmod 0644 {} +
as_user docker build --pull -t sheetkeeper-sandbox:pilot /opt/sheetkeeper/sandbox
install -d -o sheetkeeper -g sheetkeeper -m 0700 /var/lib/sheetkeeper
if [[ ! -e /etc/sheetkeeper.env ]]; then
  cat > /etc/sheetkeeper.env <<EOF
SHEETKEEPER_ENABLE_INFERENCE=0
SHEETKEEPER_REQUIRE_ROOTLESS=1
SHEETKEEPER_IMAGE=sheetkeeper-sandbox:pilot
SHEETKEEPER_INFERENCE_BUDGET_FILE=/var/lib/sheetkeeper/inference-budget.json
SHEETKEEPER_INFERENCE_MAX_CALLS=10
SHEETKEEPER_DEPLOYMENT_PROVIDER=vultr
VULTR_INFERENCE_API_KEY=
VULTR_INFERENCE_MODEL=qwen3.8-flash-next
SHEETKEEPER_ACCESS_CODE=
SHEETKEEPER_ALLOWED_HOST=
EOF
fi
chown root:sheetkeeper /etc/sheetkeeper.env
chmod 0640 /etc/sheetkeeper.env
cat > /etc/systemd/system/sheetkeeper.service <<EOF
[Unit]
Description=SheetKeeper isolated analysis controller
After=network-online.target user@${sk_uid}.service
Requires=user@${sk_uid}.service
[Service]
User=sheetkeeper
Group=sheetkeeper
WorkingDirectory=/opt/sheetkeeper
Environment=PYTHONPATH=/opt/sheetkeeper/src
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=DOCKER_HOST=unix:///run/user/${sk_uid}/docker.sock
Environment=XDG_RUNTIME_DIR=/run/user/${sk_uid}
EnvironmentFile=/etc/sheetkeeper.env
ExecStart=/usr/bin/python3 -m sheetkeeper.server --host 127.0.0.1 --port 8765
Restart=on-failure
RestartSec=3
UMask=0077
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ReadWritePaths=/var/lib/sheetkeeper
MemoryMax=256M
TasksMax=64
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now sheetkeeper.service
as_user docker image inspect --format '{{.Id}}' sheetkeeper-sandbox:pilot
printf 'Controller is loopback-only. Configure private env/TLS before public access.\n'
