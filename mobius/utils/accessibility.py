"""Accessibility checker — WCAG 2.1 Mobile guidelines."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from appium.webdriver.common.appiumby import AppiumBy

from mobius.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class A11yViolation:
    element_id: str
    issue: str
    severity: str = "warning"


@dataclass
class A11yReport:
    violations: list[A11yViolation] = field(default_factory=list)
    passed: int = 0
    elements_checked: int = 0

    def add_violation(self, elem_id: str, issue: str, severity: str = "warning") -> None:
        self.violations.append(A11yViolation(elem_id, issue, severity))

    def add_pass(self) -> None:
        self.passed += 1

    @property
    def has_errors(self) -> bool:
        return any(v.severity == "error" for v in self.violations)

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0

    def summary(self) -> str:
        lines = [
            f"A11y: {self.elements_checked} checked, "
            f"{self.passed} passed, {len(self.violations)} violations"
        ]
        for v in self.violations:
            lines.append(f"  [{v.severity.upper()}] {v.element_id}: {v.issue}")
        return "\n".join(lines)


class AccessibilityChecker:
    """
    Проверяет базовые требования доступности (WCAG 2.1 Mobile).

    Args:
        driver: Appium-драйвер.
        max_elements: лимит элементов для проверки (по умолчанию 100).
                      Предотвращает зависание на сложных экранах.
        density_factor: пикселей на один dp (420dpi → 2.625). По умолчанию
                      спрашивается с устройства через `wm density`; если
                      получить не удалось, проверка размеров не выполняется —
                      сравнивать пиксели с нормой в dp нельзя.
    """

    MIN_TOUCH_TARGET_DP = 44  # Apple HIG / Material Design
    REFERENCE_DPI = 160  # mdpi: 1dp == 1px

    _DENSITY_PATTERNS = (
        re.compile(r"Override density:\s*(\d+)"),
        re.compile(r"Physical density:\s*(\d+)"),
    )

    def __init__(
        self,
        driver: Any,
        max_elements: int = 100,
        density_factor: float | None = None,
    ) -> None:
        self._driver = driver
        self._max_elements = max_elements
        self._density_factor = density_factor
        self._density_resolved = density_factor is not None

    def check_screen(self) -> A11yReport:
        """Проверяет текущий экран. Лимит: max_elements (дефолт 100)."""
        report = A11yReport()
        try:
            elements = self._driver.find_elements(AppiumBy.XPATH, "//*")
        except Exception as e:
            logger.warning("check_screen: find_elements('//*') failed: %s", e)
            return report

        # Ограничиваем количество элементов — //* на сложном экране = 500+
        min_px = self._min_touch_target_px()
        for elem in elements[: self._max_elements]:
            try:
                self._record(elem, report, min_px)
            except Exception as e:
                # DEBUG: элемент мог устареть (StaleElement) между find_elements
                # и проверкой — обычное дело на динамическом UI, не поломка.
                logger.debug("check_screen: skipping one element (likely stale): %s", e)

        return report

    def check_element(self, elem: Any) -> A11yReport:
        """Проверяет один конкретный элемент."""
        report = A11yReport()
        try:
            self._record(elem, report, self._min_touch_target_px())
        except Exception as e:
            logger.debug("check_element: check failed for element (likely stale): %s", e)
        return report

    def _record(self, elem: Any, report: A11yReport, min_px: int | None) -> None:
        """Один элемент — одна строка отчёта: нарушения либо зачёт."""
        violations = self._check_element(elem, min_px)
        report.elements_checked += 1
        for violation in violations:
            report.add_violation(violation.element_id, violation.issue, violation.severity)
        if not violations:
            report.add_pass()

    def _check_element(self, elem: Any, min_px: int | None = None) -> list[A11yViolation]:
        tag = elem.tag_name or "unknown"
        elem_id = elem.get_attribute("resource-id") or tag

        clickable = elem.get_attribute("clickable") == "true"
        content_desc = elem.get_attribute("content-desc") or ""
        text = elem.text or ""
        violations: list[A11yViolation] = []

        # 1. Кликабельные без content-desc и без текста → ошибка
        if clickable and not content_desc and not text:
            violations.append(
                A11yViolation(elem_id, "Clickable element missing content-desc", "error")
            )

        # 2. Минимальный touch target (только когда известна плотность — см. docstring)
        if clickable and min_px is not None:
            size = elem.size
            w = size.get("width", 0)
            h = size.get("height", 0)
            if w < min_px or h < min_px:
                violations.append(
                    A11yViolation(
                        elem_id,
                        f"Touch target too small: {w}x{h}px "
                        f"(min {min_px}px = {self.MIN_TOUCH_TARGET_DP}dp)",
                        "warning",
                    )
                )

        # 3. Картинки без alt-текста → ошибка
        if "image" in tag.lower() and elem.is_displayed() and not text and not content_desc:
            violations.append(
                A11yViolation(elem_id, "Image missing content-desc (alt text)", "error")
            )

        return violations

    def _min_touch_target_px(self) -> int | None:
        """
        Нижняя граница touch target в пикселях, None если плотность неизвестна.

        `elem.size` Appium отдаёт в пикселях, а 44 — это dp: сравнение чисел
        из разных систем координат флагало каждую кнопку на плотном экране и
        не флагало ничего на mdpi.
        """
        if not self._density_resolved:
            self._density_factor = self._query_density_factor()
            self._density_resolved = True
        if self._density_factor is None:
            return None
        return round(self.MIN_TOUCH_TARGET_DP * self._density_factor)

    def _query_density_factor(self) -> float | None:
        """Плотность экрана с устройства: `wm density` → dpi / 160."""
        try:
            out = self._driver.execute_script(
                "mobile: shell",
                {"command": "wm", "args": ["density"]},
            )
        except Exception as e:
            logger.warning(
                "_query_density_factor: couldn't read screen density (%s) — "
                "touch target sizes will not be checked. Pass density_factor "
                "explicitly to enable the rule.",
                e,
            )
            return None

        text = str(out)
        for pattern in self._DENSITY_PATTERNS:
            match = pattern.search(text)
            if match:
                dpi = int(match.group(1))
                if dpi > 0:
                    return dpi / self.REFERENCE_DPI
        logger.warning(
            "_query_density_factor: unrecognized 'wm density' output %r — "
            "touch target sizes will not be checked.",
            text,
        )
        return None

    def assert_no_errors(self, report: A11yReport) -> None:
        """Падаем если есть errors (не warnings)."""
        if report.has_errors:
            errors = [v for v in report.violations if v.severity == "error"]
            msg = "\n".join(f"  {v.element_id}: {v.issue}" for v in errors)
            raise AssertionError(f"Accessibility errors found:\n{msg}")

    def assert_no_violations(self, report: A11yReport) -> None:
        """Падаем на любые нарушения (включая warnings)."""
        if report.has_violations:
            msg = "\n".join(
                f"  [{v.severity}] {v.element_id}: {v.issue}" for v in report.violations
            )
            raise AssertionError(f"Accessibility violations found:\n{msg}")
