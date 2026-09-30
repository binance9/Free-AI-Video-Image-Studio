from __future__ import annotations

import contextlib
import io
import sys
import threading
import time
from collections import defaultdict, deque
from typing import Callable


class _ThreadStream(io.TextIOBase):
    def __init__(self, original, broker: "JobLogBroker", channel: str):
        # pythonw.exe intentionally has no console streams. Keep a harmless
        # sink so model/subprocess output can still be forwarded to web SSE.
        self.original, self.broker, self.channel = original or io.StringIO(), broker, channel
        self._parts = threading.local()

    def write(self, value):
        written = self.original.write(value)
        binding = self.broker.binding()
        if binding and value:
            pending = getattr(self._parts, "value", "") + str(value)
            chunks = pending.replace("\r", "\n").split("\n")
            self._parts.value = chunks.pop()
            for chunk in chunks:
                if chunk.strip():
                    self.broker.publish(*binding, chunk.strip(), self.channel)
        return written

    def flush(self):
        return self.original.flush()

    def __getattr__(self, name):
        return getattr(self.original, name)


class JobLogBroker:
    def __init__(self):
        self._local = threading.local()
        self._lock = threading.RLock()
        self._events = defaultdict(lambda: deque(maxlen=5000))
        self._seq = 0
        self._installed = False

    def install(self):
        if self._installed:
            return
        self._installed = True
        sys.stdout = _ThreadStream(sys.stdout, self, "stdout")
        sys.stderr = _ThreadStream(sys.stderr, self, "stderr")

    def binding(self):
        return getattr(self._local, "job", None)

    @contextlib.contextmanager
    def capture(self, scope: str, job_id: str):
        previous = self.binding()
        self._local.job = (scope, job_id)
        try:
            yield
        except Exception:
            import traceback
            self.publish(scope, job_id, traceback.format_exc(), "stderr", "error")
            raise
        finally:
            self._local.job = previous

    def bound(self, scope: str, job_id: str, target: Callable):
        def run(*args, **kwargs):
            with self.capture(scope, job_id):
                return target(*args, **kwargs)
        return run

    def publish(self, scope: str, job_id: str, message: str, channel="stdout", level=None):
        clean = str(message).strip()
        if not clean:
            return
        lower = clean.lower()
        if level:
            inferred = level
        elif any(word in lower for word in ("traceback", "error", "exception", "cuda out of memory", "failed")):
            inferred = "error"
        elif any(word in lower for word in ("warning", "deprecated", "truncated")):
            inferred = "warning"
        else:
            inferred = "debug"
        with self._lock:
            self._seq += 1
            self._events[(scope, job_id)].append({"seq": self._seq, "time": time.time(), "channel": channel, "level": inferred, "message": clean})

    def after(self, scope: str, job_id: str, cursor: int):
        with self._lock:
            return [dict(item) for item in self._events[(scope, job_id)] if item["seq"] > cursor]


job_log_broker = JobLogBroker()
