"""Unit tests — gestures."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

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
class TestGesturesMocked:
    def setup_method(self):
        self.d = MagicMock()
        self.d.get_window_size.return_value = S
        self.g = Gestures(self.d)

    def test_swipe_calls_window_size(self):
        with patch.object(self.g, "_w3c_swipe"):
            self.g.swipe(SwipeDirection.UP)
        self.d.get_window_size.assert_called_once()

    @pytest.mark.parametrize("direction", list(SwipeDirection))
    def test_all_swipes_call_w3c(self, direction):
        with patch.object(self.g, "_w3c_swipe") as m:
            self.g.swipe(direction)
        m.assert_called_once()

    def test_swipe_custom_duration(self):
        with patch.object(self.g, "_w3c_swipe") as m:
            self.g.swipe(SwipeDirection.UP, duration_ms=800)
        assert m.call_args[0][4] == 800

    def test_swipe_to_element_first_try(self):
        elem = MagicMock()
        self.d.find_element.return_value = elem
        assert self.g.swipe_to_element(("id", "x")) == elem

    def test_swipe_to_element_timeout(self):
        from selenium.common.exceptions import NoSuchElementException

        self.d.find_element.side_effect = NoSuchElementException()
        with patch.object(self.g, "_w3c_swipe"):
            with pytest.raises(TimeoutError):
                self.g.swipe_to_element(("id", "x"), max_attempts=2)

    def test_swipe_to_element_succeeds_after_retries(self):
        from selenium.common.exceptions import NoSuchElementException

        elem = MagicMock()
        calls = [0]

        def find(by, val):
            calls[0] += 1
            if calls[0] < 3:
                raise NoSuchElementException()
            return elem

        self.d.find_element.side_effect = find
        with patch.object(self.g, "_w3c_swipe"):
            result = self.g.swipe_to_element(("id", "x"), max_attempts=5)
        assert result == elem

    def test_pinch_calls_w3c(self):
        with patch.object(self.g, "_w3c_swipe") as m:
            self.g.pinch(0.5)
        m.assert_called_once()


@pytest.mark.unit
class TestGesturesW3CActions:
    """Покрываем W3C Actions через mock ActionChains/ActionBuilder."""

    def setup_method(self):
        self.d = MagicMock()
        self.d.get_window_size.return_value = S
        self.g = Gestures(self.d)

    def _make_mocks(self):
        pa = MagicMock()
        ka = MagicMock()
        ab_instance = MagicMock()
        ab_instance.pointer_action = pa
        ab_instance.key_action = ka
        MockAB = MagicMock(return_value=ab_instance)

        ac = MagicMock()
        ac.perform = MagicMock()
        type(ac).w3c_actions = property(
            lambda self: ab_instance,
            lambda self, v: None,
        )
        MockAC = MagicMock(return_value=ac)
        return MockAC, MockAB, ac, ab_instance, pa, ka

    def test_long_press(self):
        MockAC, MockAB, ac, ab, pa, ka = self._make_mocks()
        with (
            patch("mobius.utils.gestures.ActionChains", MockAC),
            patch("mobius.utils.gestures.ActionBuilder", MockAB),
        ):
            self.g.long_press(MagicMock(), duration_ms=1000)
        pa.pointer_down.assert_called_once()
        pa.release.assert_called_once()
        ka.pause.assert_called_once_with(1.0)
        ac.perform.assert_called_once()

    def test_long_press_at(self):
        MockAC, MockAB, ac, ab, pa, ka = self._make_mocks()
        with (
            patch("mobius.utils.gestures.ActionChains", MockAC),
            patch("mobius.utils.gestures.ActionBuilder", MockAB),
        ):
            self.g.long_press_at(100, 200, 1500)
        pa.move_to_location.assert_called_once_with(100, 200)
        ac.perform.assert_called_once()

    def test_double_tap(self):
        MockAC, MockAB, ac, ab, pa, ka = self._make_mocks()
        with (
            patch("mobius.utils.gestures.ActionChains", MockAC),
            patch("mobius.utils.gestures.ActionBuilder", MockAB),
        ):
            self.g.double_tap(MagicMock())
        assert pa.pointer_down.call_count == 2
        assert pa.release.call_count == 2
        ac.perform.assert_called_once()

    def test_drag_and_drop(self):
        MockAC, MockAB, ac, ab, pa, ka = self._make_mocks()
        with (
            patch("mobius.utils.gestures.ActionChains", MockAC),
            patch("mobius.utils.gestures.ActionBuilder", MockAB),
        ):
            self.g.drag_and_drop(MagicMock(), MagicMock())
        pa.pointer_down.assert_called_once()
        pa.release.assert_called_once()
        assert ka.pause.call_count == 2
        ac.perform.assert_called_once()

    def test_w3c_swipe_direct(self):
        with patch("mobius.utils.gestures.ActionBuilder") as AB:
            ab_inst = MagicMock()
            AB.return_value = ab_inst
            self.g._w3c_swipe(100, 200, 300, 400, 500)
        ab_inst.pointer_action.move_to_location.assert_any_call(100, 200)
        ab_inst.perform.assert_called_once()
