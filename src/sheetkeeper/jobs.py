"""Bounded in-memory job registry for the preparation UI; no public listing."""
import hashlib
import secrets
import threading
import time
from .contracts import inspect_csv, validate_result
from .planner import make_plan


class Jobs:
    def __init__(self, sandbox):
        self.sandbox = sandbox
        self.lock = threading.Lock()
        self.jobs = {}
        self.active = False
        self.blocked = False

    def plan(self, csv_text, question, mode, locale="pt-BR"):
        metadata = inspect_csv(csv_text)
        with self.lock:
            # Expire capabilities after one hour. Source data never becomes a public artifact.
            self.jobs = {k: v for k, v in self.jobs.items() if time.time() - v['created'] < 3600}
            if len(self.jobs) >= 20 or self.active or self.blocked:
                raise ValueError("A demonstração está ocupada ou requer revisão do sandbox.")
            job_id = secrets.token_urlsafe(24)
            self.jobs[job_id] = {"id": job_id, "created": time.time(), "status": "planning", "csv": csv_text,
                                 "metadata": metadata, "events": [], "code": "", "provider": {},
                                 "result": None, "receipt": None, "summary": ""}
        try:
            plan, provider = make_plan(metadata, question, mode, locale)
            with self.lock:
                self.jobs[job_id].update(status="ready", summary=plan["summary"], code=plan["code"], provider=provider)
                self.jobs[job_id]["events"].append("Plano pronto para revisão. Nenhum código executado.")
            return self.get(job_id)
        except Exception:
            with self.lock:
                self.jobs.pop(job_id, None)
            raise

    def get(self, job_id):
        with self.lock:
            if job_id not in self.jobs or time.time() - self.jobs[job_id]['created'] >= 3600:
                raise KeyError("Tarefa não encontrada.")
            # Raw CSV and creation metadata are not returned after upload.
            return {k: v for k, v in self.jobs[job_id].items() if k not in {"csv", "created"}}

    def run(self, job_id, containment=False):
        ready = self.sandbox.preflight()
        if not ready["ready"]:
            raise ValueError(ready["reason"])
        with self.lock:
            if self.active or self.blocked:
                raise ValueError("Há uma execução em andamento ou limpeza pendente.")
            job = self.jobs[job_id]
            if time.time() - job['created'] >= 3600:
                raise KeyError("Tarefa expirada.")
            if job["status"] != "ready":
                raise ValueError("Este plano já foi executado. Crie uma nova tarefa.")
            self.active = True
            job["status"] = "running"
            code = "while True:\n    pass\n" if containment else job["code"]
            job["executed_code"] = code
            job["events"].append("Teste de contenção: loop infinito dentro do sandbox." if containment else "Executando em ambiente isolado.")
        threading.Thread(target=self._execute, args=(job_id, code, containment), daemon=True).start()
        return self.get(job_id)

    def _execute(self, job_id, code, containment):
        job = self.jobs[job_id]
        try:
            output = self.sandbox.execute(code, job["csv"], timeout=3 if containment else 15)
            valid = None
            if output["exit_code"] == 0 and not output["timed_out"] and output["destroyed"]:
                valid = validate_result(output["result"])
                if valid["rows"] != job["metadata"]["rows"]:
                    raise ValueError("O resultado não cobre todas as linhas de entrada.")
            status = "contained" if containment and output["timed_out"] and output["destroyed"] else (
                "completed" if valid else "failed")
            receipt = {"execution": "docker", "provider": job["provider"], "containment_test": containment,
                       "input_sha256": hashlib.sha256(job["csv"].encode()).hexdigest(),
                       "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
                       "status": status, "container": output["container"], "image_id": output["image_id"],
                       "destroyed": output["destroyed"], "timed_out": output["timed_out"],
                       "exit_code": output["exit_code"], "elapsed_ms": output["elapsed_ms"],
                       "limits": {"memory_mib": 256, "cpu": 1, "pids": 64, "network": "none"},
                       "numeric_cross_check": "rows and sum of groups; semantic correctness still requires human review"}
            with self.lock:
                job.update(status=status, result=valid, receipt=receipt)
                self.blocked = not output["destroyed"]
                job["events"].append("Ambiente destruído." if output["destroyed"] else "Limpeza falhou. Novas execuções bloqueadas.")
                if status == "failed":
                    job["events"].append("A tarefa não produziu um resultado validado.")
        except Exception:
            with self.lock:
                job.update(status="failed")
                job["events"].append("Falha de execução ou validação. Consulte o operador antes de repetir.")
                # If runtime failed before a cleanup proof, fail closed.
                self.blocked = True
        finally:
            with self.lock:
                job["csv"] = ""
                self.active = False
