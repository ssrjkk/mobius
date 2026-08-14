"""Accessibility checker — WCAG 2.1 Mobile guidelines."""

from __future__ import annotations

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
        max_elements: лимит элементов для проверки (по умолчанию 100).
                      Предотвращает зависание на сложных экранах.
    """

    MIN_TOUCH_TARGET = 44  # dp — Apple HIG / Material Design

    def __init__(self, driver: Any, max_elements: int = 100) -> None:
        self._driver = driver
        self._max_elements = max_elements

    def check_screen(self) -> A11yReport:
        """Проверяет текущий экран. Лимит: max_elements (дефолт 100)."""
        report = A11yReport()
        try:
            elements = self._driver.find_elements(AppiumBy.XPATH, "//*")
        except Exception as e:
            logger.warning("check_screen: find_elements('//*') failed: %s", e)
            return report

        # Ограничиваем количество элементов — //* на сложном экране = 500+
        elements = elements[: self._max_elements]
        report.elements_checked = len(elements)

        for elem in elements:
            try:
                self._check_element(elem, report)
            except Exception as e:
                # DEBUG: элемент мог устареть (StaleElement) между find_elements
                # и проверкой — обычное дело на динамическом UI, не поломка.
                logger.debug("check_screen: skipping one element (likely stale): %s", e)

        return report

    def check_element(self, elem: Any) -> A11yReport:
        """Проверяет один конкретный элемент."""
        report = A11yReport()
        report.elements_checked = 1
        try:
            self._check_element(elem, report)
        except Exception as e:
            logger.debug("check_element: check failed for element (likely stale): %s", e)
        return report  # pragma: no branch

    def _check_element(self, elem: Any, report: A11yReport) -> None:
        tag = elem.tag_name or "unknown"
        elem_id = elem.get_attribute("resource-id") or tag

        clickable = elem.get_attribute("clickable") == "true"
        content_desc = elem.get_attribute("content-desc") or ""
        text = elem.text or ""

        # 1. Кликабельные без content-desc и без текста → ошибка
        if clickable and not content_desc and not text:
            report.add_violation(elem_id, "Clickable element missing content-desc", "error")
        else:
            report.add_pass()

        # 2. Минимальный touch target 44dp
        if clickable:
            size = elem.size
            w = size.get("width", 0)
            h = size.get("height", 0)
            if w < self.MIN_TOUCH_TARGET or h < self.MIN_TOUCH_TARGET:
                report.add_violation(
                    elem_id,
                    f"Touch target too small: {w}x{h}dp (min {self.MIN_TOUCH_TARGET}dp)",
                    "warning",
                )

        # 3. Картинки без alt-текста → ошибка
        displayed = elem.is_displayed()
        if displayed and not text and not content_desc:
            if "Image" in tag or "image" in tag.lower():
                report.add_violation(
                    elem_id,
                    "Image missing content-desc (alt text)",
                    "error",
                )

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
