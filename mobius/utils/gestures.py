"""Mobile gestures — W3C Actions API."""

from __future__ import annotations

from enum import Enum
from typing import Any

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions import interaction
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput

from mobius.types import Locator


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
                    raise TimeoutError(
                        f"Element {locator} not found after {max_attempts} swipes"
                    ) from exc
                self.swipe(direction, duration_ms=300)
        return None  # pragma: no cover

    def long_press(self, element: Any, duration_ms: int = 1500) -> None:
        action = ActionChains(self._driver)
        action.w3c_actions = ActionBuilder(
            self._driver, mouse=PointerInput(interaction.POINTER_TOUCH, "touch")
        )
        action.w3c_actions.pointer_action.move_to(element)
        action.w3c_actions.pointer_action.pointer_down()
        action.w3c_actions.key_action.pause(duration_ms / 1000)
        action.w3c_actions.pointer_action.release()
        action.perform()

    def long_press_at(self, x: int, y: int, duration_ms: int = 1500) -> None:
        action = ActionChains(self._driver)
        action.w3c_actions = ActionBuilder(
            self._driver, mouse=PointerInput(interaction.POINTER_TOUCH, "touch")
        )
        action.w3c_actions.pointer_action.move_to_location(x, y)
        action.w3c_actions.pointer_action.pointer_down()
        action.w3c_actions.key_action.pause(duration_ms / 1000)
        action.w3c_actions.pointer_action.release()
        action.perform()

    def double_tap(self, element: Any) -> None:
        action = ActionChains(self._driver)
        action.w3c_actions = ActionBuilder(
            self._driver, mouse=PointerInput(interaction.POINTER_TOUCH, "touch")
        )
        for _ in range(2):
            action.w3c_actions.pointer_action.move_to(element)
            action.w3c_actions.pointer_action.pointer_down()
            action.w3c_actions.pointer_action.release()
            action.w3c_actions.key_action.pause(0.1)
        action.perform()

    def drag_and_drop(self, source: Any, target: Any) -> None:
        action = ActionChains(self._driver)
        action.w3c_actions = ActionBuilder(
            self._driver, mouse=PointerInput(interaction.POINTER_TOUCH, "touch")
        )
        action.w3c_actions.pointer_action.move_to(source)
        action.w3c_actions.pointer_action.pointer_down()
        action.w3c_actions.key_action.pause(0.5)
        action.w3c_actions.pointer_action.move_to(target)
        action.w3c_actions.key_action.pause(0.3)
        action.w3c_actions.pointer_action.release()
        action.perform()

    def pinch(self, scale: float = 0.5) -> None:
        size = self._driver.get_window_size()
        cx, cy = size["width"] // 2, size["height"] // 2
        offset = int(min(cx, cy) * 0.3)
        self._w3c_swipe(cx - offset, cy, int(cx - offset * scale), cy, 500)

    def _w3c_swipe(self, sx: int, sy: int, ex: int, ey: int, duration_ms: int) -> None:
        finger = PointerInput(interaction.POINTER_TOUCH, "finger")
        action = ActionBuilder(self._driver, mouse=finger)
        action.pointer_action.move_to_location(sx, sy)
        action.pointer_action.pointer_down()
        action.key_action.pause(duration_ms / 1000)
        action.pointer_action.move_to_location(ex, ey)
        action.pointer_action.release()
        action.perform()

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
