"""
V2V-SCADA Lightweight Real-Time Performance Instrumentation
============================================================
Provides non-blocking execution profiling and metrics tracking across
the telemetry pipeline without impacting real-time latency (<1 microsecond overhead).

Strictly categorizes every operational dimension into:
- DESIGN TARGET (Engineering design requirement)
- MEASURED (Actively measured in running software)
- NOT MEASURED (Awaiting hardware test bench or specific profiler)
"""

import time
import threading
from typing import Dict, Any


class LatencyTracker:
    """Thread-safe rolling accumulator for microsecond-accurate latency measurements."""
    def __init__(self, name: str, design_target_ms: float):
        self.name = name
        self.design_target_ms = design_target_ms
        self.count = 0
        self.total_ms = 0.0
        self.min_ms = float('inf')
        self.max_ms = 0.0
        self.last_ms = 0.0
        self._lock = threading.Lock()

    def record(self, duration_ms: float) -> None:
        with self._lock:
            self.count += 1
            self.total_ms += duration_ms
            self.last_ms = duration_ms
            if duration_ms < self.min_ms:
                self.min_ms = duration_ms
            if duration_ms > self.max_ms:
                self.max_ms = duration_ms

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            if self.count == 0:
                return {
                    "status": "NOT MEASURED",
                    "design_target_ms": self.design_target_ms,
                    "samples": 0,
                    "avg_ms": None,
                    "min_ms": None,
                    "max_ms": None,
                    "last_ms": None
                }
            return {
                "status": "MEASURED",
                "design_target_ms": self.design_target_ms,
                "samples": self.count,
                "avg_ms": round(self.total_ms / self.count, 3),
                "min_ms": round(self.min_ms, 3),
                "max_ms": round(self.max_ms, 3),
                "last_ms": round(self.last_ms, 3)
            }


class MetricsCollector:
    """Central singleton collecting performance and throughput statistics."""
    def __init__(self):
        # Latency trackers with design target latencies
        self.telemetry_pipeline = LatencyTracker("telemetry_pipeline", design_target_ms=5.0)
        self.collision_physics = LatencyTracker("collision_physics", design_target_ms=1.5)
        self.database_write = LatencyTracker("database_write", design_target_ms=10.0)
        self.websocket_push = LatencyTracker("websocket_push", design_target_ms=2.0)

        # Counter trackers
        self.packets_ingested = 0
        self.packets_rejected_security = 0
        self.collision_checks_performed = 0
        self.start_time = time.time()
        self._lock = threading.Lock()

    def inc_ingested(self) -> None:
        with self._lock:
            self.packets_ingested += 1

    def inc_rejected(self) -> None:
        with self._lock:
            self.packets_rejected_security += 1

    def inc_collision_checks(self) -> None:
        with self._lock:
            self.collision_checks_performed += 1

    def get_summary(self) -> Dict[str, Any]:
        uptime_sec = max(1.0, time.time() - self.start_time)
        with self._lock:
            ingested = self.packets_ingested
            rejected = self.packets_rejected_security
            collision_checks = self.collision_checks_performed

        rate_hz = round(ingested / uptime_sec, 2)

        return {
            "uptime_seconds": round(uptime_sec, 1),
            "throughput": {
                "telemetry_rate_hz": {
                    "status": "MEASURED" if ingested > 0 else "NOT MEASURED",
                    "design_target_hz": 10.0,
                    "measured_value": rate_hz
                },
                "total_packets_ingested": ingested,
                "total_security_rejections": rejected,
                "total_collision_checks": collision_checks
            },
            "latencies": {
                "telemetry_processing_latency": self.telemetry_pipeline.snapshot(),
                "collision_calculation_latency": self.collision_physics.snapshot(),
                "database_write_latency": self.database_write.snapshot(),
                "websocket_broadcast_latency": self.websocket_push.snapshot()
            },
            "hardware_rf_metrics": {
                "sx1281_over_the_air_latency": {
                    "status": "DESIGN TARGET",
                    "design_target": "< 3.0 ms",
                    "measured": None,
                    "note": "Requires dual physical STM32 oscilloscope / logic analyzer bench measurement."
                },
                "rf_transmission_range_m": {
                    "status": "DESIGN TARGET",
                    "design_target": "1000 - 2000 meters line-of-sight",
                    "measured": None,
                    "note": "Requires open outdoor test-track field verification."
                },
                "rf_packet_loss_percent": {
                    "status": "NOT MEASURED",
                    "design_target": "< 1.0 % at 500m",
                    "measured": None,
                    "note": "Awaiting physical RF bench telemetry counting."
                }
            }
        }


# Global Singleton
metrics = MetricsCollector()
