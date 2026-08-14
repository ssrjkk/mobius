"""Unit tests — AppResetHelper и ResetStrategy."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mobius.driver.capabilities import ResetStrategy
from mobius.utils.test_isolation import AppResetHelper


def _helper(terminate_fails: bool = False, activate_fails: bool = False) -> tuple:
    d = MagicMock()
    if terminate_fails:
        d.terminate_app.side_effect = Exception("not running")
    if activate_fails:
        d.activate_app.side_effect = Exception("activation failed")
    d.capabilities = {"appium:app": "/path/to/app.apk"}
    return d, AppResetHelper(d, "com.example.app")


@pytest.mark.unit
class TestResetStrategyEnum:
    def test_all_values_defined(self):
        for s in (
            ResetStrategy.NONE,
            ResetStrategy.TERMINATE,
            ResetStrategy.FULL_RESET,
            ResetStrategy.NO_RESET,
        ):
            assert s.value

    def test_terminate_is_default_recommendation(self):
        """Документированный дефолт — убеждаемся что не поменяли случайно."""
        assert ResetStrategy.TERMINATE == "terminate"


@pytest.mark.unit
class TestIsolationNone:
    def test_none_strategy_returns_true(self):
        d, h = _helper()
        assert h.reset(ResetStrategy.NONE) is True

    def test_none_strategy_does_not_touch_driver(self):
        d, h = _helper()
        h.reset(ResetStrategy.NONE)
        d.terminate_app.assert_not_called()
        d.activate_app.assert_not_called()


@pytest.mark.unit
class TestIsolationTerminate:
    def test_terminate_calls_terminate_and_activate(self):
        d, h = _helper()
        result = h.reset(ResetStrategy.TERMINATE)
        assert result is True
        d.terminate_app.assert_called_once_with("com.example.app")
        d.activate_app.assert_called_once_with("com.example.app")

    def test_terminate_survives_terminate_failure(self):
        d, h = _helper(terminate_fails=True)
        result = h.reset(ResetStrategy.TERMINATE)
        assert result is True  # продолжает без terminate
        d.activate_app.assert_called_once()

    def test_terminate_returns_false_when_activate_fails(self):
        d, h = _helper(activate_fails=True)
        result = h.reset(ResetStrategy.TERMINATE)
        assert result is False

    def test_terminate_is_default_strategy(self):
        d, h = _helper()
        h.reset()  # без явного аргумента
        d.terminate_app.assert_called_once()
        d.activate_app.assert_called_once()


@pytest.mark.unit
class TestIsolationFullReset:
    def test_full_reset_removes_and_reinstalls(self):
        d, h = _helper()
        result = h.reset(ResetStrategy.FULL_RESET)
        assert result is True
        d.remove_app.assert_called_once_with("com.example.app")
        d.install_app.assert_called_once_with("/path/to/app.apk")
        d.activate_app.assert_called_once()

    def test_full_reset_without_app_path_returns_false(self):
        d, h = _helper()
        d.capabilities = {}  # нет appium:app
        result = h.reset(ResetStrategy.FULL_RESET)
        assert result is False
        d.install_app.assert_not_called()

    def test_full_reset_survives_remove_failure(self):
        d, h = _helper()
        d.remove_app.side_effect = Exception("not installed")
        result = h.reset(ResetStrategy.FULL_RESET)
        assert result is True  # продолжает к install


@pytest.mark.unit
class TestIsolationClearData:
    def test_clear_app_data_calls_pm_clear(self):
        d, h = _helper()
        result = h.clear_app_data()
        assert result is True
        d.execute_script.assert_called_once_with(
            "mobile: shell",
            {"command": "pm", "args": ["clear", "com.example.app"]},
        )
        d.activate_app.assert_called_once()

    def test_clear_app_data_returns_false_on_exception(self):
        d, h = _helper()
        d.execute_script.side_effect = Exception("shell not supported")
        result = h.clear_app_data()
        assert result is False


@pytest.mark.unit
class TestResetEdgeCases:
    def test_unknown_strategy_returns_false(self):
        d, h = _helper()
        # Используем string напрямую — не из enum
        result = h.reset("unknown_strategy")  # type: ignore[arg-type]
        assert result is False

    def test_no_reset_strategy_returns_true_no_driver_calls(self):
        d, h = _helper()
        result = h.reset(ResetStrategy.NO_RESET)
        assert result is True
        d.terminate_app.assert_not_called()
        d.activate_app.assert_not_called()

    def test_full_reset_install_fails_returns_false(self):
        d, h = _helper()
        d.install_app.side_effect = Exception("no space left on device")
        result = h.reset(ResetStrategy.FULL_RESET)
        assert result is False
