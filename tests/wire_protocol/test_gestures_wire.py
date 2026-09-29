"""
Wire-protocol тесты жестов — реальные байты W3C Actions на проводе.

gestures.py исторически ставил паузу long_press/double_tap/drag в key-трек.
W3C исполняет трэки тик-за-тиком параллельно, а ActionBuilder.perform()
выбрасывает трэки с пустым списком действий, поэтому key-пауза не удерживала
палец опущенным: long_press уходил на сервер как обычный тап. Mock-тесты этого
не видели — MagicMock ничего не сериализует. Здесь проверяется JSON, который
реально принял бы Appium.
"""

from __future__ import annotations

from typing import Any

import pytest

from mobius.utils.gestures import Gestures, SwipeDirection
from tests.wire_protocol.fake_webdriver_server import FakeWebDriverServer


def _action_tracks(server: FakeWebDriverServer) -> list[dict[str, Any]]:
    requests = server.requests_matching("POST", "/actions")
    assert requests, "ни одного POST /actions — жест не ушёл на сервер"
    body = requests[-1].body
    assert body is not None
    return body["actions"]


def _track(tracks: list[dict[str, Any]], name: str = "finger") -> list[dict[str, Any]]:
    for track in tracks:
        if track["id"] == name:
            return track["actions"]
    raise AssertionError(f"no pointer track {name!r} in {[t['id'] for t in tracks]}")


def _types(actions: list[dict[str, Any]]) -> list[str]:
    return [a["type"] for a in actions]


def _held_milliseconds(actions: list[dict[str, Any]]) -> int:
    """Сумма пауз, стоящих МЕЖДУ pointerDown и pointerUp, то есть с зажатым пальцем."""
    types = _types(actions)
    between = actions[types.index("pointerDown") + 1 : types.index("pointerUp")]
    return sum(a["duration"] for a in between if a["type"] == "pause")


@pytest.mark.wire_protocol
class TestOnlyPointerTracks:
    """Корень бага: key-трек создавался молча и служил контейнером для пауз."""

    @pytest.mark.parametrize(
        "apply_gesture",
        [
            pytest.param(lambda g, e: g.long_press(e, 1500), id="long_press"),
            pytest.param(lambda g, e: g.long_press_at(10, 20, 1500), id="long_press_at"),
            pytest.param(lambda g, e: g.double_tap(e), id="double_tap"),
            pytest.param(lambda g, e: g.drag_and_drop(e, e), id="drag_and_drop"),
            pytest.param(lambda g, e: g.swipe(SwipeDirection.UP), id="swipe"),
            pytest.param(lambda g, e: g.pinch(0.5), id="pinch"),
        ],
    )
    def test_server_sees_pointer_tracks_only(self, wire_driver, wire_server, apply_gesture):
        apply_gesture(Gestures(wire_driver), wire_driver.find_element("id", "x"))
        assert {t["type"] for t in _action_tracks(wire_server)} == {"pointer"}


@pytest.mark.wire_protocol
class TestLongPress:
    def test_pause_sits_on_the_pointer_track_between_down_and_up(self, wire_driver, wire_server):
        Gestures(wire_driver).long_press(wire_driver.find_element("id", "btn"), duration_ms=1500)

        actions = _track(_action_tracks(wire_server))
        assert _types(actions) == ["pointerMove", "pointerDown", "pause", "pointerUp"]
        assert _held_milliseconds(actions) == 1500

    def test_duration_is_configurable(self, wire_driver, wire_server):
        Gestures(wire_driver).long_press(wire_driver.find_element("id", "btn"), duration_ms=3000)
        assert _track(_action_tracks(wire_server))[2]["duration"] == 3000

    def test_at_moves_to_absolute_coordinates(self, wire_driver, wire_server):
        Gestures(wire_driver).long_press_at(100, 200, duration_ms=1200)

        actions = _track(_action_tracks(wire_server))
        assert (actions[0]["x"], actions[0]["y"]) == (100, 200)
        assert _held_milliseconds(actions) == 1200


@pytest.mark.wire_protocol
class TestDoubleTap:
    def test_two_down_up_pairs_on_one_finger(self, wire_driver, wire_server):
        Gestures(wire_driver).double_tap(wire_driver.find_element("id", "cell"))

        actions = _track(_action_tracks(wire_server))
        assert _types(actions).count("pointerDown") == 2
        assert _types(actions).count("pointerUp") == 2

    def test_gap_between_taps_happens_while_finger_is_up(self, wire_driver, wire_server):
        Gestures(wire_driver).double_tap(wire_driver.find_element("id", "cell"))

        assert _types(_track(_action_tracks(wire_server))) == [
            "pointerMove",
            "pointerDown",
            "pause",
            "pointerUp",
            "pause",
            "pointerMove",
            "pointerDown",
            "pause",
            "pointerUp",
            "pause",
        ]

    def test_each_tap_holds_the_finger_down(self, wire_driver, wire_server):
        Gestures(wire_driver).double_tap(wire_driver.find_element("id", "cell"))

        actions = _track(_action_tracks(wire_server))
        first_tap = actions[: _types(actions).index("pointerUp")]
        assert [a["duration"] for a in first_tap if a["type"] == "pause"] == [50]


@pytest.mark.wire_protocol
class TestDragAndDrop:
    def test_finger_stays_down_across_the_move(self, wire_driver, wire_server):
        source = wire_driver.find_element("id", "source")
        Gestures(wire_driver).drag_and_drop(source, source, hold_ms=400)

        actions = _track(_action_tracks(wire_server))
        types = _types(actions)
        assert types.index("pointerDown") < types.index("pointerMove", 1) < types.index("pointerUp")
        assert _held_milliseconds(actions) == 800


@pytest.mark.wire_protocol
class TestSwipe:
    def test_move_duration_carries_the_swipe_speed(self, wire_driver, wire_server):
        Gestures(wire_driver).swipe(SwipeDirection.UP, duration_ms=700)

        moves = [a for a in _track(_action_tracks(wire_server)) if a["type"] == "pointerMove"]
        assert [m["duration"] for m in moves] == [700, 700]
        assert (moves[0]["x"], moves[0]["y"]) == (540, 1920)
        assert (moves[1]["x"], moves[1]["y"]) == (540, 480)

    def test_direction_changes_the_vector(self, wire_driver, wire_server):
        Gestures(wire_driver).swipe(SwipeDirection.LEFT, duration_ms=300)

        moves = [a for a in _track(_action_tracks(wire_server)) if a["type"] == "pointerMove"]
        assert moves[0]["x"] > moves[1]["x"]
        assert moves[0]["y"] == moves[1]["y"]


@pytest.mark.wire_protocol
class TestPinch:
    def test_two_fingers_not_one_swipe(self, wire_driver, wire_server):
        Gestures(wire_driver).pinch(scale=0.5, duration_ms=500)

        tracks = _action_tracks(wire_server)
        assert [t["id"] for t in tracks] == ["finger-left", "finger-right"]
        assert all(t["parameters"]["pointerType"] == "touch" for t in tracks)

    @pytest.mark.parametrize(
        "scale,converging",
        [(0.5, True), (2.0, False)],
        ids=["zoom_out", "zoom_in"],
    )
    def test_fingers_move_toward_or_away_from_each_other(
        self, wire_driver, wire_server, scale, converging
    ):
        Gestures(wire_driver).pinch(scale=scale)

        tracks = _action_tracks(wire_server)
        left = [a["x"] for a in tracks[0]["actions"] if a["type"] == "pointerMove"]
        right = [a["x"] for a in tracks[1]["actions"] if a["type"] == "pointerMove"]
        assert (left[0] < left[1]) is converging
        assert (right[0] > right[1]) is converging

    def test_both_fingers_press_and_release(self, wire_driver, wire_server):
        Gestures(wire_driver).pinch(scale=0.5)

        for track in _action_tracks(wire_server):
            assert _types(track["actions"]) == [
                "pointerMove",
                "pointerDown",
                "pointerMove",
                "pointerUp",
            ]
