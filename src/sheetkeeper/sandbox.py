"""Disposable Docker execution. The controller never runs user/generated code."""
import json
import os
import shutil
import selectors
import subprocess
import threading
import time
import uuid
from .contracts import MAX_CODE_BYTES, MAX_CSV_BYTES

# This wrapper is executed INSIDE the container. Only bounded JSON leaves it.
WRAPPER = r'''
import json, os, resource, signal, stat, subprocess, sys
payload = json.load(sys.stdin)
os.chdir('/work')
with open('analysis.py', 'w') as f: f.write(payload['code'])
with open('data.csv', 'w') as f: f.write(payload['csv'])
os.chmod('data.csv', 0o444)
resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
timed_out = False
with open('stdout.log', 'wb') as out, open('stderr.log', 'wb') as err:
    process = subprocess.Popen([sys.executable, '-I', 'analysis.py'], stdout=out, stderr=err, start_new_session=True)
    try: process.wait(timeout=payload['timeout'])
    except subprocess.TimeoutExpired:
        timed_out = True
    finally:
        try: os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        process.wait()
def read_regular(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit: raise ValueError('invalid artifact')
        return f.read(limit + 1).decode('utf-8', errors='replace')
result = None
try:
    if not timed_out and process.returncode == 0: result = json.loads(read_regular('result.json', 65536))
except (OSError, ValueError): pass
def log(path):
    try: return read_regular(path, 1024 * 1024)[:4096]
    except (OSError, ValueError): return '[log unavailable]'
print(json.dumps({'exit_code': process.returncode, 'timed_out': timed_out, 'stdout': log('stdout.log'),
                  'stderr': log('stderr.log'), 'result': result}, allow_nan=False))
'''


def bounded_capture(command, payload, deadline):
    """Kill the attachment on time/output limit; the caller destroys its container."""
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    def feed():
        try:
            process.stdin.write(payload)
            process.stdin.close()
        except (OSError, ValueError):
            pass
    writer = threading.Thread(target=feed, daemon=True)
    writer.start()
    output = bytearray()
    timeout_hit = limited = False
    end = time.monotonic() + deadline
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, True)
            selector.register(process.stderr, selectors.EVENT_READ, False)
            count = 0
            while selector.get_map():
                left = end - time.monotonic()
                if left <= 0:
                    timeout_hit = True
                    break
                for key, _ in selector.select(min(left, .2)):
                    chunk = os.read(key.fileobj.fileno(), 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    count += len(chunk)
                    if count > 200_000:
                        limited = True
                        break
                    if key.data:
                        output.extend(chunk)
                if limited:
                    break
            if timeout_hit or limited:
                process.kill()
            try:
                process.wait(timeout=max(.1, end - time.monotonic()))
            except subprocess.TimeoutExpired:
                timeout_hit = True
                process.kill()
                process.wait(timeout=2)
    finally:
        for stream in (process.stdout, process.stderr):
            stream.close()
        writer.join(timeout=.2)
    return bytes(output), process.returncode, timeout_hit, limited


class DockerSandbox:
    def __init__(self, image=None, binary=None):
        self.binary = binary or shutil.which("docker")
        self.image = image or os.environ.get("SHEETKEEPER_IMAGE", "sheetkeeper-sandbox:prep")
        self.image_id = None

    def preflight(self):
        if not self.binary:
            return {"ready": False, "reason": "Docker não está disponível. Nenhum código será executado."}
        try:
            info = subprocess.run([self.binary, "info", "--format", "{{json .}}"], capture_output=True,
                                  timeout=4, check=True)
            details = json.loads(info.stdout)
            if details.get("OSType") != "linux":
                raise ValueError("Use um daemon Docker Linux.")
            if details.get("Warnings"):
                raise ValueError("Resolva os avisos do daemon sobre limites antes de executar.")
            # Production profile requires rootless; the local preparation can use Docker Desktop's Linux VM.
            if os.environ.get("SHEETKEEPER_REQUIRE_ROOTLESS") == "1" and not any(
                    "rootless" in str(x) for x in details.get("SecurityOptions", [])):
                raise ValueError("A implantação exige Docker rootless.")
            image = subprocess.run([self.binary, "image", "inspect", "--format", "{{.Id}}", self.image],
                                   capture_output=True, timeout=4, check=True).stdout.decode().strip()
            if not image.startswith("sha256:"):
                raise ValueError("A imagem local não pôde ser identificada.")
            self.image_id = image
            return {"ready": True, "reason": "Sandbox disponível.", "image_id": image,
                    "memory_mib": 256, "cpu": 1, "pids": 64, "network": "none"}
        except (OSError, subprocess.SubprocessError, ValueError):
            self.image_id = None
            return {"ready": False, "reason": "Ative o Docker e construa a imagem de sandbox para executar. Sem fallback no computador."}

    def command(self, name):
        if not self.image_id:
            raise RuntimeError("Faça o preflight antes da execução.")
        return [self.binary, "run", "--name", name, "--label", "org.figueira.sheetkeeper=prep",
                "--pull=never", "--network=none", "--read-only", "--user=10001:10001", "--cap-drop=ALL",
                "--security-opt=no-new-privileges=true", "--cpus=1", "--memory=256m", "--memory-swap=256m",
                "--pids-limit=64", "--ipc=private", "--ulimit", "nofile=64:64", "--ulimit", "core=0:0",
                "--tmpfs", "/work:rw,nosuid,nodev,noexec,size=16m,mode=1777",
                "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=8m,mode=1777",
                "--log-driver=none", "-i", self.image_id, "python", "-I", "-c", WRAPPER]

    def execute(self, code, csv_text, timeout=15):
        if len(code.encode()) > MAX_CODE_BYTES or len(csv_text.encode()) > MAX_CSV_BYTES:
            raise ValueError("A tarefa excede os limites de execução.")
        if not 1 <= timeout <= 15:
            raise ValueError("Timeout fora dos limites.")
        name = "sheetkeeper-" + uuid.uuid4().hex
        payload = json.dumps({"code": code, "csv": csv_text, "timeout": timeout}).encode()
        started = time.monotonic()
        result = {"exit_code": None, "timed_out": False, "stdout": "", "stderr": "", "result": None}
        cleanup = False
        try:
            raw, exit_code, timeout_hit, limited = bounded_capture(self.command(name), payload, timeout + 8)
            try:
                value = json.loads(raw) if not limited and not timeout_hit else None
            except (ValueError, UnicodeDecodeError):
                value = None
            if exit_code == 0 and isinstance(value, dict) and set(value) == set(result):
                result = value
            else:
                result["stderr"] = "O sandbox falhou ou excedeu um limite."
                result["timed_out"] = timeout_hit
        finally:
            # No caller-supplied identifier is passed to Docker. Destroy the exact disposable name.
            try:
                removed = subprocess.run([self.binary, "rm", "--force", name], capture_output=True, timeout=5)
                cleanup = removed.returncode == 0
            except (OSError, subprocess.SubprocessError):
                cleanup = False
        return {**result, "container": name, "image_id": self.image_id,
                "elapsed_ms": round((time.monotonic() - started) * 1000), "destroyed": cleanup}
