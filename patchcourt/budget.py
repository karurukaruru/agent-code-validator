"""Persistent request reservations for an explicitly started experiment session.

Reservations happen before transport and are never refunded. A crash or timeout
therefore cannot silently open an unbounded retry loop. Not a billing estimate.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
import threading

from .evidence import now, read_json, write_json


_APPLIED_LOCK = threading.RLock()


@contextmanager
def _ledger_lock(path):
    """OS-owned lock: concurrent runners fail closed; a crash releases it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_name(path.name + ".lock").open("a+b") as handle:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ValueError("Experiment budget ledger is already in use; no request sent") from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class RequestBudget:
    def __init__(self, path, *, model_calls=30, searches=10, discovery_calls=5):
        self.path = Path(path).resolve()
        self.lock = threading.Lock()
        limits = {"model_calls": model_calls, "searches": searches, "discovery_calls": discovery_calls}
        if any(type(n) is not int or n < 0 or n > 100 for n in limits.values()):
            raise ValueError("Invalid experiment request limits")
        self.limits = limits
        with _ledger_lock(self.path):
            if self.path.exists():
                self.state = self._read_state()
            else:
                self.state = {"created_at": now(), "limits": limits, "reservations": [],
                              "scope": "Request reservations, not a dollar-cost estimate. No automatic retries."}
                self._persist()

    def _read_state(self):
        state = read_json(self.path)
        if (not isinstance(state, dict) or state.get("limits") != self.limits
                or any(type(n) is not int for n in state.get("limits", {}).values())
                or not isinstance(state.get("reservations"), list)):
            raise ValueError("Experiment budget identity differs from the saved ledger")
        for row in state["reservations"]:
            if not isinstance(row, dict) or not isinstance(row.get("kind"), str) or row["kind"] not in self.limits:
                raise ValueError("Experiment budget ledger contains an invalid reservation")
        return state

    def _persist(self):
        """Atomic replacement preserves the previous ledger if writing fails."""
        descriptor, temporary = tempfile.mkstemp(prefix=".budget-", suffix=".tmp", dir=self.path.parent)
        os.close(descriptor)
        target = Path(temporary)
        try:
            write_json(target, self.state)
            os.replace(target, self.path)
        finally:
            target.unlink(missing_ok=True)

    def reserve(self, provider, payload=None, endpoint="chat/completions"):
        kind = "searches" if provider == "tavily" else "discovery_calls" if endpoint == "models" else "model_calls"
        if provider == "tavily" and (not isinstance(payload, dict) or payload.get("search_depth", "basic") != "basic"):
            raise ValueError("This experiment budget permits Tavily basic search only")
        if kind == "model_calls" and (not isinstance(payload, dict) or type(payload.get("max_tokens")) is not int
                                      or not 1 <= payload["max_tokens"] <= 8192):
            raise ValueError("Budgeted model requests require max_tokens between 1 and 8192")
        with self.lock, _ledger_lock(self.path):
            # Other instances/processes may have reserved since construction.
            self.state = self._read_state()
            used = sum(row["kind"] == kind for row in self.state["reservations"])
            if used >= self.state["limits"][kind]:
                raise ValueError("Experiment " + kind + " budget exhausted; no request sent")
            self.state["reservations"].append({"kind": kind, "provider": provider,
                                                "model": payload.get("model") if isinstance(payload, dict) else None,
                                                "max_tokens": payload.get("max_tokens") if kind == "model_calls" else None,
                                                "reserved_at": now()})
            self._persist()

    @contextmanager
    def applied(self):
        from . import providers
        if not _APPLIED_LOCK.acquire(blocking=False):
            raise ValueError("Another experiment budget context is active in this process")
        original = providers.request
        def bounded(provider, payload=None, endpoint="chat/completions"):
            self.reserve(provider, payload, endpoint)
            return original(provider, payload, endpoint)
        providers.request = bounded
        try:
            yield self
        finally:
            providers.request = original
            _APPLIED_LOCK.release()
