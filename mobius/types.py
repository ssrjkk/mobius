"""
Общие type aliases для framework.

Locator — пара (стратегия, значение), например (AppiumBy.ID, "com.app:id/btn").
Появляется в сигнатурах по всему коду (screens, elements, gestures, finder) —
вынесен сюда один раз вместо `tuple[str, str]` в каждом файле.
"""

from __future__ import annotations

from typing import Any

Locator = tuple[str, str]
Capabilities = dict[str, Any]
