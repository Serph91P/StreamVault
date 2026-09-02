"""Low-cardinality service metrics for the StreamVault process."""

from __future__ import annotations

from threading import Lock
from typing import Final


_ROUTE_GROUPS: Final[tuple[tuple[str, str], ...]] = (
    ("/api/recording/", "api_recording"),
    ("/api/recordings", "api_recordings"),
    ("/api/background-queue/", "api_background_queue"),
    ("/api/health", "api_health"),
    ("/api/auth", "api_auth"),
    ("/api/streamers", "api_streamers"),
    ("/api/streams", "api_streams"),
    ("/api/", "api_other"),
)


class ServiceMetrics:
    """Collect process-local metrics without user or request identifiers."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, float] = {}
        self._request_counts: dict[tuple[str, str, str], int] = {}
        self._request_duration_sums: dict[tuple[str, str, str], float] = {}
        self._active_recordings = 0
        self._queue_depth = 0

    @staticmethod
    def route_group(route: str) -> str:
        for prefix, group in _ROUTE_GROUPS:
            if route.startswith(prefix):
                return group
        return "non_api"

    @staticmethod
    def status_group(status_code: int) -> str:
        return f"{status_code // 100}xx"

    def record_request(
        self, *, method: str, route: str, status_code: int, duration_seconds: float
    ) -> None:
        labels = (
            method.upper(),
            self.route_group(route),
            self.status_group(status_code),
        )
        with self._lock:
            self._request_counts[labels] = self._request_counts.get(labels, 0) + 1
            self._request_duration_sums[labels] = self._request_duration_sums.get(
                labels, 0.0
            ) + max(0.0, duration_seconds)

    def recording_started(self) -> None:
        self._increment("recording_starts")

    def recording_stopped(self, *, duration_seconds: float | None = None) -> None:
        self._increment("recording_stops")
        if duration_seconds is not None:
            with self._lock:
                self._counters["recording_duration_seconds_count"] = (
                    self._counters.get("recording_duration_seconds_count", 0) + 1
                )
                self._counters["recording_duration_seconds_sum"] = self._counters.get(
                    "recording_duration_seconds_sum", 0.0
                ) + max(0.0, duration_seconds)

    def recording_failed(self) -> None:
        self._increment("recording_failures")

    def record_lease_contention(self) -> None:
        self._increment("lease_contention")

    def record_lease_recovery(self, count: int = 1) -> None:
        if count > 0:
            with self._lock:
                self._counters["lease_recovery"] = (
                    self._counters.get("lease_recovery", 0) + count
                )

    def set_active_recordings(self, count: int) -> None:
        with self._lock:
            self._active_recordings = max(0, count)

    def set_queue_depth(self, depth: int) -> None:
        with self._lock:
            self._queue_depth = max(0, depth)

    def _increment(self, name: str) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + 1

    def render_prometheus(self) -> str:
        """Render a deterministic Prometheus text exposition without secrets."""
        with self._lock:
            lines = [
                "# TYPE streamvault_recording_starts_total counter",
                f"streamvault_recording_starts_total {self._counters.get('recording_starts', 0)}",
                "# TYPE streamvault_recording_stops_total counter",
                f"streamvault_recording_stops_total {self._counters.get('recording_stops', 0)}",
                "# TYPE streamvault_recording_failures_total counter",
                f"streamvault_recording_failures_total {self._counters.get('recording_failures', 0)}",
                "# TYPE streamvault_recording_duration_seconds summary",
                "streamvault_recording_duration_seconds_count "
                f"{self._counters.get('recording_duration_seconds_count', 0)}",
                "streamvault_recording_duration_seconds_sum "
                f"{self._counters.get('recording_duration_seconds_sum', 0)}",
                "# TYPE streamvault_active_local_recordings gauge",
                f"streamvault_active_local_recordings {self._active_recordings}",
                "# TYPE streamvault_lease_contention_total counter",
                f"streamvault_lease_contention_total {self._counters.get('lease_contention', 0)}",
                "# TYPE streamvault_lease_recovery_total counter",
                f"streamvault_lease_recovery_total {self._counters.get('lease_recovery', 0)}",
                "# TYPE streamvault_background_queue_depth gauge",
                f"streamvault_background_queue_depth {self._queue_depth}",
                "# TYPE streamvault_http_requests_total counter",
            ]
            for (method, route, status), count in sorted(self._request_counts.items()):
                labels = f'method="{method}",route="{route}",status="{status}"'
                lines.append(f"streamvault_http_requests_total{{{labels}}} {count}")
                lines.append(
                    f"streamvault_http_request_duration_seconds_count{{{labels}}} "
                    f"{count}"
                )
                lines.append(
                    f"streamvault_http_request_duration_seconds_sum{{{labels}}} "
                    f"{self._request_duration_sums[(method, route, status)]}"
                )
        return "\n".join(lines) + "\n"


service_metrics = ServiceMetrics()
