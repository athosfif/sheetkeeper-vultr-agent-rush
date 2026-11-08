"""Preparation server. Local by default; no generated code runs in this process."""
import argparse
import hmac
import json
import os
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from .jobs import Jobs
from .localization import translate
from .sandbox import DockerSandbox
from .budget import budget_status

ROOT = Path(__file__).resolve().parents[2]
JOBS = Jobs(DockerSandbox())
PLANNING_SLOTS = threading.BoundedSemaphore(1)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, *args):
        pass  # Do not log job capability URLs, private code or input.

    def send(self, status, body, content_type="application/json; charset=utf-8", download=False):
        if content_type.startswith("application/json") and not isinstance(body, bytes):
            if isinstance(body, dict) and "error" in body:
                body = {**body, "error_source": body["error"], "error": translate(body["error"], self.headers.get("X-SheetKeeper-Locale", "pt-BR"))}
            body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        if download:
            self.send_header("Content-Disposition", 'attachment; filename="sheetkeeper-evidence.json"')
        self.end_headers()
        self.wfile.write(body)

    def allowed(self, api=True):
        host = self.headers.get("Host", "")
        if host not in self.server.allowed_hosts:
            self.send(403, {"error": "Origem não permitida."})
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in self.server.allowed_origins:
            self.send(403, {"error": "Origem não permitida."})
            return False
        if api and self.server.access_code:
            expected = "Bearer " + self.server.access_code
            if not hmac.compare_digest(self.headers.get("Authorization", ""), expected):
                self.send(401, {"error": "Informe o código privado da demonstração."})
                return False
        return True

    def do_GET(self):
        path = urlsplit(self.path).path
        if not self.allowed(api=path.startswith("/api/")):
            return
        assets = {"/": ("index.html", "text/html; charset=utf-8"),
                  "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                  "/locale.js": ("locale.js", "text/javascript; charset=utf-8"),
                  "/i18n.json": ("i18n.json", "application/json; charset=utf-8"),
                  "/style.css": ("style.css", "text/css; charset=utf-8")}
        if path in assets:
            filename, content_type = assets[path]
            self.send(200, (ROOT / "web" / filename).read_bytes(), content_type)
        elif path == "/api/status":
            provider = os.environ.get("SHEETKEEPER_DEPLOYMENT_PROVIDER", "")
            self.send(200, {"stage": "deployed" if provider == "vultr" else "preparation", "sandbox": JOBS.sandbox.preflight(),
                            "inference_enabled": os.environ.get("SHEETKEEPER_ENABLE_INFERENCE") == "1",
                            "cloud_deployed": provider == "vultr", "max_csv_bytes": 200_000,
                            "deployment_claim_source": "server_configuration",
                            "inference_budget": budget_status()})
        elif path == "/api/sample":
            self.send(200, {"csv": (ROOT / "fixtures" / "sales.csv").read_text()})
        elif path.startswith("/api/jobs/"):
            parts = path.split("/")
            try:
                if len(parts) not in (4, 5) or (len(parts) == 5 and parts[4] != "evidence"):
                    raise KeyError()
                job = JOBS.get(parts[3])
                if len(parts) == 5:
                    if not job["receipt"]:
                        self.send(409, {"error": "Ainda não há comprovante de execução."})
                        return
                    self.send(200, {"receipt": job["receipt"], "result": job["result"],
                                    "executed_code": job.get("executed_code"), "events": job["events"]}, download=True)
                else:
                    self.send(200, job)
            except KeyError:
                self.send(404, {"error": "Tarefa não encontrada ou expirada."})
        else:
            self.send(404, {"error": "Página não encontrada."})

    def do_POST(self):
        if not self.allowed():
            return
        if self.headers.get("Transfer-Encoding"):
            self.send(400, {"error": "Use um pedido com tamanho definido."})
            return
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            self.send(415, {"error": "Envie JSON."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 450_000:
                raise ValueError("Pedido vazio ou muito grande.")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("Pedido inválido.")
            path = urlsplit(self.path).path
            if path == "/api/plan":
                if not PLANNING_SLOTS.acquire(blocking=False):
                    self.send(429, {"error": "Já há um plano em preparação. Tente novamente depois."})
                    return
                try:
                    result = JOBS.plan(data.get("csv"), data.get("question"), data.get("mode"), self.headers.get("X-SheetKeeper-Locale", "pt-BR"))
                finally:
                    PLANNING_SLOTS.release()
                self.send(200, result)
            elif path == "/api/run":
                if not isinstance(data.get("job_id"), str) or type(data.get("containment", False)) is not bool:
                    raise ValueError("Pedido de execução inválido.")
                self.send(202, JOBS.run(data["job_id"], data.get("containment", False)))
            else:
                self.send(404, {"error": "Operação não encontrada."})
        except (ValueError, UnicodeDecodeError) as exc:
            self.send(400, {"error": str(exc) if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError) else "JSON inválido."})
        except KeyError:
            self.send(404, {"error": "Tarefa não encontrada."})
        except Exception:
            self.send(500, {"error": "Não foi possível concluir. Nenhum resultado é apresentado como validado."})


def create_server(host="127.0.0.1", port=8765):
    access_code = os.environ.get("SHEETKEEPER_ACCESS_CODE", "")
    public_host = os.environ.get("SHEETKEEPER_ALLOWED_HOST", "")
    if host not in {"127.0.0.1", "localhost", "::1"} and (len(access_code) < 24 or not public_host):
        raise ValueError("Para acesso externo, configure código privado de ao menos 24 caracteres e hostname autorizado.")
    server = ThreadingHTTPServer((host, port), Handler)
    server.allowed_hosts = {"127.0.0.1:" + str(server.server_port), "localhost:" + str(server.server_port)}
    if public_host:
        server.allowed_hosts.add(public_host)
    server.allowed_origins = {scheme + "://" + h for h in server.allowed_hosts for scheme in ("http", "https")}
    server.access_code = access_code
    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = create_server(args.host, args.port)
    print(f"SheetKeeper controller: http://{args.host}:{server.server_port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
