"""Persistent call reservations, outside the worker and public source package.

A reservation is charged before the provider request and never refunded. This
caps attempts, including timeouts; it is not a provider billing meter. The file
must live on persistent local storage owned by the controller service account.
"""
import fcntl
import json
import os
from pathlib import Path
import stat

UNAVAILABLE = "Não foi possível verificar o limite de consultas. Nenhuma chamada foi enviada."
EXHAUSTED = "O limite de consultas desta demonstração foi atingido. Nenhuma chamada foi enviada."


def _config():
    raw = os.environ.get("SHEETKEEPER_INFERENCE_MAX_CALLS", "10")
    value = os.environ.get("SHEETKEEPER_INFERENCE_BUDGET_FILE", "")
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        raise ValueError(UNAVAILABLE) from None
    if not 1 <= limit <= 500 or not value or not Path(value).is_absolute():
        raise ValueError(UNAVAILABLE)
    return Path(value), limit


def _read(fd):
    details = os.fstat(fd)
    if (not stat.S_ISREG(details.st_mode) or details.st_uid != os.geteuid()
            or details.st_mode & 0o022 or details.st_size > 4096):
        raise ValueError(UNAVAILABLE)
    os.lseek(fd, 0, os.SEEK_SET)
    try:
        record = json.loads(os.read(fd, 4097))
    except (ValueError, UnicodeDecodeError):
        raise ValueError(UNAVAILABLE) from None
    if (not isinstance(record, dict) or set(record) != {"version", "calls"}
            or type(record["version"]) is not int or record["version"] != 1
            or type(record["calls"]) is not int or not 0 <= record["calls"] <= 500):
        raise ValueError(UNAVAILABLE)
    return record["calls"]


def _snapshot(used, limit):
    return {"ready": True, "used": used, "limit": limit,
            "remaining": max(0, limit - used), "unit": "reserved_provider_attempts"}


def reserve_attempt():
    """Atomically persist one attempt before network; fail closed on any error."""
    fd = None
    try:
        path, limit = _config()
        flags = os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW
        try:
            fd = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o600)
            created = True
        except FileExistsError:
            fd = os.open(path, flags)
            created = False
        fcntl.flock(fd, fcntl.LOCK_EX)
        used = 0 if created else _read(fd)
        if used >= limit:
            raise ValueError(EXHAUSTED)
        record = json.dumps({"version": 1, "calls": used + 1}).encode()
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        written = os.write(fd, record)
        if written != len(record):
            raise ValueError(UNAVAILABLE)
        os.fsync(fd)
        # Make the new directory entry durable as well, before a provider call.
        if created:
            parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
        return _snapshot(used + 1, limit)
    except OSError:
        raise ValueError(UNAVAILABLE) from None
    finally:
        if fd is not None:
            os.close(fd)  # releases flock, including on an exhausted budget


def budget_status():
    """Read-only metadata. Never reveal the private path or initialize a file."""
    fd = None
    try:
        path, limit = _config()
        try:
            fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        except FileNotFoundError:
            if not path.parent.is_dir() or not os.access(path.parent, os.W_OK):
                raise ValueError(UNAVAILABLE)
            return _snapshot(0, limit)
        fcntl.flock(fd, fcntl.LOCK_SH)
        return _snapshot(_read(fd), limit)
    except (OSError, ValueError):
        return {"ready": False, "reason": "budget_unavailable"}
    finally:
        if fd is not None:
            os.close(fd)
