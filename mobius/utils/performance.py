"""Performance metrics — startup time, action timing (Google RAIL model)."""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from mobius.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceReport:
    metrics: dict[str, float] = field(default_factory=dict)

    def add(self, name: str, value_ms: float) -> None:
        self.metrics[name] = round(value_ms, 2)

    def get(self, name: str) -> float | None:
        return self.metrics.get(name)

    def assert_under(self, name: str, threshold_ms: float) -> None:
        value = self.metrics.get(name)
        if value is None:
            raise KeyError(f"Metric '{name}' not found")
        assert value <= threshold_ms, (
            f"Performance regression: {name} = {value}ms > {threshold_ms}ms threshold"
        )

    def summary(self) -> str:
        lines = ["Performance Metrics:"]
        for name, ms in sorted(self.metrics.items()):
            lines.append(f"  {name}: {ms}ms")
        return "\n".join(lines)


class PerformanceCollector:
    # Google RAIL model thresholds
    THRESHOLDS = {
        "app_startup": 5_000,
        "screen_load": 2_000,
        "tap_response": 100,
        "scroll_fps": 16,
        "api_response": 3_000,
    }

    def __init__(self, driver: Any) -> None:
        self._driver = driver
        self.report = PerformanceReport()

    @contextmanager
    def measure(self, metric_name: str) -> Generator[None, None, None]:
        start = time.perf_counter()
        yield
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.report.add(metric_name, elapsed_ms)

    def measure_app_startup(self, app_package: str) -> float:
        try:
            self._driver.terminate_app(app_package)
        except Exception as e:
            # DEBUG: приложение часто ещё не запущено при первом измерении —
            # это ожидаемо, не проблема.
            logger.debug(
                "measure_app_startup('%s'): terminate_app failed "
                "(app likely wasn't running yet): %s",
                app_package,
                e,
            )
        start = time.perf_counter()
        self._driver.activate_app(app_package)
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.report.add("app_startup", elapsed_ms)
        return elapsed_ms

    def assert_all_thresholds(self) -> None:
        for name, _value in self.report.metrics.items():
            if name in self.THRESHOLDS:
                self.report.assert_under(name, self.THRESHOLDS[name])
