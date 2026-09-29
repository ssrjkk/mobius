"""Mobile gestures — W3C Actions API.

Каждый жест собирается на ОДНОМ pointer-треке. W3C выполняет последовательность
«тиками»: действие с индексом N одного устройства идёт параллельно с действием
с индексом N другого. Пауза, поставленная в key-трек, сдвигает по времени
только key-трек, поэтому pointerDown и pointerUp в соседних тиках сливаются в
обычный тап, и long_press перестаёт быть долгим нажатием. Проверено на реальном
проводе — tests/wire_protocol/test_gestures_wire.py.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.actions import interaction
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_actions import PointerActions
from selenium.webdriver.common.actions.pointer_input import PointerInput

from mobius.types import Locator

TAP_HOLD_SECONDS = 0.05
TAP_GAP_SECONDS = 0.1


class SwipeDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


class Gestures:
    """Утилиты для мобильных жестов через W3C Actions API (Appium 2.x+)."""

    def __init__(self, driver: Any) -> None:
        self._driver = driver

    def swipe(
        self,
        direction: SwipeDirection,
        duration_ms: int = 500,
        start_ratio: float = 0.8,
        end_ratio: float = 0.2,
    ) -> None:
        size = self._driver.get_window_size()
        sx, sy, ex, ey = self.calculate_swipe_coords(size, direction, start_ratio, end_ratio)
        self._w3c_swipe(sx, sy, ex, ey, duration_ms)

    def swipe_to_element(
        self,
        locator: Locator,
        direction: SwipeDirection = SwipeDirection.UP,
        max_attempts: int = 10,
    ) -> Any:
        from selenium.common.exceptions import NoSuchElementException

        for attempt in range(max_attempts):
            try:
                return self._driver.find_element(*locator)
            except NoSuchElementException as exc:
                if attempt == max_attempts - 1:
                    raise TimeoutException(
                        f"Element {locator} not found after {max_attempts} swipes"
                    ) from exc
                self.swipe(direction, duration_ms=300)
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")

    def long_press(self, element: Any, duration_ms: int = 1500) -> None:
        builder = self._builder(duration_ms)
        finger = builder.pointer_action
        finger.move_to(element)
        finger.pointer_down()
        finger.pause(duration_ms / 1000)
        finger.release()
        builder.perform()

    def long_press_at(self, x: int, y: int, duration_ms: int = 1500) -> None:
        builder = self._builder(duration_ms)
        finger = builder.pointer_action
        finger.move_to_location(x, y)
        finger.pointer_down()
        finger.pause(duration_ms / 1000)
        finger.release()
        builder.perform()

    def double_tap(self, element: Any) -> None:
        builder = self._builder()
        finger = builder.pointer_action
        for _ in range(2):
            finger.move_to(element)
            finger.pointer_down()
            finger.pause(TAP_HOLD_SECONDS)
            finger.release()
            finger.pause(TAP_GAP_SECONDS)
        builder.perform()

    def drag_and_drop(self, source: Any, target: Any, hold_ms: int = 500) -> None:
        builder = self._builder(hold_ms)
        finger = builder.pointer_action
        finger.move_to(source)
        finger.pointer_down()
        finger.pause(hold_ms / 1000)
        finger.move_to(target)
        finger.pause(hold_ms / 1000)
        finger.release()
        builder.perform()

    def pinch(self, scale: float = 0.5, duration_ms: int = 500) -> None:
        """Двумя пальцами: scale < 1 — свести, scale > 1 — развести."""
        size = self._driver.get_window_size()
        cx, cy = size["width"] // 2, size["height"] // 2
        offset = int(min(cx, cy) * 0.3)
        spread = int(offset * scale)

        left = PointerInput(interaction.POINTER_TOUCH, "finger-left")
        builder = ActionBuilder(self._driver, mouse=left, duration=duration_ms)
        right = builder.add_pointer_input(interaction.POINTER_TOUCH, "finger-right")
        fingers = (builder.pointer_action, PointerActions(right, duration=duration_ms))
        starts = (cx - offset, cx + offset)
        ends = (cx - spread, cx + spread)

        for actions, start_x in zip(fingers, starts, strict=True):
            actions.move_to_location(start_x, cy)
        for actions in fingers:
            actions.pointer_down()
        for actions, end_x in zip(fingers, ends, strict=True):
            actions.move_to_location(end_x, cy)
        for actions in fingers:
            actions.release()
        builder.perform()

    def _w3c_swipe(self, sx: int, sy: int, ex: int, ey: int, duration_ms: int) -> None:
        builder = self._builder(duration_ms)
        finger = builder.pointer_action
        finger.move_to_location(sx, sy)
        finger.pointer_down()
        finger.move_to_location(ex, ey)
        finger.release()
        builder.perform()

    def _builder(self, duration_ms: int = 250) -> ActionBuilder:
        """ActionBuilder с единственным touch-пальцем вместо курсорной мыши."""
        return ActionBuilder(
            self._driver,
            mouse=PointerInput(interaction.POINTER_TOUCH, "finger"),
            duration=duration_ms,
        )

    @staticmethod
    def calculate_swipe_coords(
        size: dict[str, int],
        direction: SwipeDirection,
        start_ratio: float = 0.8,
        end_ratio: float = 0.2,
    ) -> tuple[int, int, int, int]:
        """Чистая функция вычисления координат свайпа — легко тестировать."""
        w, h = size["width"], size["height"]
        m = {
            SwipeDirection.UP: (w * 0.5, h * start_ratio, w * 0.5, h * end_ratio),
            SwipeDirection.DOWN: (w * 0.5, h * end_ratio, w * 0.5, h * start_ratio),
            SwipeDirection.LEFT: (w * start_ratio, h * 0.5, w * end_ratio, h * 0.5),
            SwipeDirection.RIGHT: (w * end_ratio, h * 0.5, w * start_ratio, h * 0.5),
        }
        sx, sy, ex, ey = m[direction]
        return int(sx), int(sy), int(ex), int(ey)
