"""Bounded, secret-free pool/SQL diagnostics for both comparison variants."""

import sys
import threading
import time

from sqlalchemy import event


class RuntimeDiagnostics:
    def __init__(self, engine):
        engine = engine.engine
        self.engine = engine
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.values = {
            "sql": 0,
            "checkouts": 0,
            "checkins": 0,
            "checked_out": 0,
            "peak_checked_out": 0,
        }
        self.dumps = []
        self.capacity = engine.pool.size() + engine.pool._max_overflow
        self.listeners = [
            ("checkout", self.checkout),
            ("checkin", self.checkin),
            ("before_cursor_execute", self.sql),
        ]
        for name, callback in self.listeners:
            event.listen(engine, name, callback)
        self.thread = threading.Thread(
            target=self.observe, name="bounded-pool-diagnostic", daemon=True
        )
        self.thread.start()

    def checkout(self, *_):
        with self.lock:
            self.values["checkouts"] += 1
            self.values["checked_out"] += 1
            self.values["peak_checked_out"] = max(
                self.values["peak_checked_out"], self.values["checked_out"]
            )

    def checkin(self, *_):
        with self.lock:
            self.values["checkins"] += 1
            self.values["checked_out"] -= 1

    def sql(self, *_):
        with self.lock:
            self.values["sql"] += 1

    def observe(self):
        while not self.stop_event.wait(1):
            if len(self.dumps) >= 8 or self.values["checked_out"] < self.capacity:
                continue
            threads = []
            for identifier, frame in list(sys._current_frames().items())[:32]:
                if identifier == threading.get_ident():
                    continue
                frames = []
                while frame is not None and len(frames) < 20:
                    frames.append(
                        {
                            "file": frame.f_code.co_filename,
                            "line": frame.f_lineno,
                            "function": frame.f_code.co_name,
                        }
                    )
                    frame = frame.f_back
                threads.append(frames)
            self.dumps.append(
                {
                    "monotonic_s": time.monotonic(),
                    "checked_out": self.values["checked_out"],
                    "threads": threads,
                }
            )

    def finish(self):
        self.stop_event.set()
        self.thread.join()
        for name, callback in self.listeners:
            event.remove(self.engine, name, callback)
        return {
            **self.values,
            "configured_capacity": self.capacity,
            "saturation_stacks": self.dumps,
        }
