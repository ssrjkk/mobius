"""
Unit tests — gestures.

Здесь только чистая арифметика и диспетчеризация (какой метод вызывает какой).
Формат W3C Actions, реально уходящий на сервер, проверяется в
tests/wire_protocol/test_gestures_wire.py: mock драйвера пропускает любой
бессмысленный payload, и именно поэтому он когда-то «зеленел» на сломанном
long_press.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from mobius.utils.gestures import Gestures, SwipeDirection

S = {"width": 1080, "height": 2400}


@pytest.mark.unit
class TestSwipeCoords:
    @pytest.mark.parametrize(
        "d,check",
        [
            (SwipeDirection.UP, lambda r: r[1] > r[3]),
            (SwipeDirection.DOWN, lambda r: r[3] > r[1]),
            (SwipeDirection.LEFT, lambda r: r[0] > r[2]),
            (SwipeDirection.RIGHT, lambda r: r[2] > r[0]),
        ],
    )
    def test_direction(self, d, check):
        assert check(Gestures.calculate_swipe_coords(S, d))

    def test_up_horizontal_center(self):
        sx, sy, ex, ey = Gestures.calculate_swipe_coords(S, SwipeDirection.UP)
        assert sx == ex == S["width"] // 2

    def test_left_vertical_center(self):
        sx, sy, ex, ey = Gestures.calculate_swipe_coords(S, SwipeDirection.LEFT)
        assert sy == ey == S["height"] // 2

    @pytest.mark.parametrize("d", list(SwipeDirection))
    def test_within_bounds(self, d):
        r = Gestures.calculate_swipe_coords(S, d)
        assert all(isinstance(v, int) for v in r)
        assert 0 <= r[0] <= S["width"] and 0 <= r[2] <= S["width"]
        assert 0 <= r[1] <= S["height"] and 0 <= r[3] <= S["height"]

    def test_custom_ratios(self):
        _, sy, _, ey = Gestures.calculate_swipe_coords(S, SwipeDirection.UP, 0.9, 0.1)
        assert sy == int(S["height"] * 0.9)
        assert ey == int(S["height"] * 0.1)


@pytest.mark.unit
class TestGesturesDispatch:
    def setup_method(self):
        self.d = MagicMock()
        self.d.get_window_size.return_value = S
        self.g = Gestures(self.d)

    def test_swipe_reads_window_size(self):
        with patch.object(self.g, "_w3c_swipe"):
            self.g.swipe(SwipeDirection.UP)
        self.d.get_window_size.assert_called_once()

    @pytest.mark.parametrize("direction", list(SwipeDirection))
    def test_all_swipes_go_through_w3c(self, direction):
        with patch.object(self.g, "_w3c_swipe") as m:
            self.g.swipe(direction)
        m.assert_called_once()

    def test_swipe_custom_duration(self):
        with patch.object(self.g, "_w3c_swipe") as m:
            self.g.swipe(SwipeDirection.UP, duration_ms=800)
        assert m.call_args[0][4] == 800

    def test_swipe_coords_match_direction(self):
        with patch.object(self.g, "_w3c_swipe") as m:
            self.g.swipe(SwipeDirection.UP)
        assert m.call_args[0][:4] == (540, 1920, 540, 480)

    def test_swipe_to_element_first_try(self):
        elem = MagicMock()
        self.d.find_element.return_value = elem
        assert self.g.swipe_to_element(("id", "x")) == elem
        self.d.get_window_size.assert_not_called()

    def test_swipe_to_element_raises_timeout_not_missing(self):
        """Вызов ловит NoSuchElementException внутри — наружу должен идти TimeoutException."""
        self.d.find_element.side_effect = NoSuchElementException()
        with patch.object(self.g, "_w3c_swipe"):
            with pytest.raises(TimeoutException, match="not found after 2 swipes"):
                self.g.swipe_to_element(("id", "x"), max_attempts=2)

    def test_swipe_to_element_succeeds_after_retries(self):
        elem = MagicMock()
        calls = {"n": 0}

        def find(_by, _val):
            calls["n"] += 1
            if calls["n"] < 3:
                raise NoSuchElementException()
            return elem

        self.d.find_element.side_effect = find
        with patch.object(self.g, "_w3c_swipe") as swipe:
            assert self.g.swipe_to_element(("id", "x"), max_attempts=5) == elem
        assert swipe.call_count == 2

    def test_swipe_to_element_zero_attempts_is_a_configuration_error(self):
        """max_attempts=0 не должен выглядеть как «элемент не найден после 0 свайпов»."""
        with pytest.raises(ValueError, match="max_attempts must be >= 1"):
            self.g.swipe_to_element(("id", "x"), max_attempts=0)

    def test_pinch_uses_screen_geometry(self):
        with patch.object(self.g, "_w3c_swipe"):
            self.g.pinch(0.5)
        self.d.get_window_size.assert_called_once()
