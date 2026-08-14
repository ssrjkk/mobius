"""
Тесты логирования — проверяют не просто "код не падает", а что при best-effort
провале в лог реально попадает диагностическое сообщение с деталями.

Это отличает production-ready framework от портфолио-версии: команда должна
видеть В ЛОГАХ CI почему device.rotate_to_landscape() тихо вернул False,
а не гадать по коду.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from mobius.elements.mobile_element import MobileElement
from mobius.logging_config import get_logger, set_level
from mobius.utils.alerts import SystemAlertHandler
from mobius.utils.biometrics import BiometricSimulator
from mobius.utils.clipboard import ClipboardManager
from mobius.utils.device import DeviceActions
from mobius.utils.file_transfer import FileTransfer
from mobius.utils.network import NetworkSimulator


@pytest.mark.unit
class TestLoggingConfig:
    def test_get_logger_returns_named_logger(self):
        logger = get_logger("mobius.utils.device")
        assert logger.name == "mobius.utils.device"

    def test_get_logger_is_child_of_mobius_namespace(self):
        logger = get_logger("mobius.utils.gestures")
        assert logger.name.startswith("mobius.")

    def test_set_level_changes_framework_logger_level(self):
        set_level(logging.DEBUG)
        assert logging.getLogger("mobius").level == logging.DEBUG
        set_level(logging.WARNING)  # restore default for other tests
        assert logging.getLogger("mobius").level == logging.WARNING

    def test_framework_logger_does_not_propagate_to_root(self):
        """
        propagate=False — важно чтобы framework не дублировал сообщения
        в root logger приложения-потребителя (двойной вывод в их CI).
        """
        assert logging.getLogger("mobius").propagate is False

    def test_repeated_get_logger_does_not_duplicate_handlers(self):
        """
        Повторные вызовы get_logger не должны плодить НАШИ handler'ы.

        Примечание: pytest сам добавляет свои handler'ы (LogCaptureHandler,
        _LiveLoggingNullHandler) на логгеры с propagate=False, чтобы caplog
        продолжал работать — это ожидаемо и не наша ответственность. Тест
        проверяет только что mobius.logging_config не плодит СВОИ
        StreamHandler'ы при повторных вызовах get_logger().
        """
        get_logger("mobius.utils.device")
        get_logger("mobius.utils.gestures")
        get_logger("mobius.utils.alerts")

        expected_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        our_handlers = [
            h
            for h in logging.getLogger("mobius").handlers
            if h.formatter is not None and getattr(h.formatter, "_fmt", "") == expected_format
        ]
        assert len(our_handlers) == 1, (
            f"Expected exactly 1 framework StreamHandler, found {len(our_handlers)}"
        )


@pytest.mark.unit
class TestSilentFailuresNowLogWarnings:
    """
    Ключевой тест production-качества: когда best-effort операция
    проваливается, в лог должно попасть WARNING с деталями — не тишина.
    """

    def test_device_reset_app_logs_warning_on_terminate_failure(self, caplog):
        d = MagicMock()
        d.capabilities = {"platformName": "Android"}
        d.terminate_app.side_effect = Exception("app was not running")
        device = DeviceActions(d)

        with caplog.at_level(logging.WARNING, logger="mobius.utils.device"):
            device.reset_app("com.example.app")

        assert len(caplog.records) == 1
        assert "reset_app" in caplog.records[0].message
        assert "com.example.app" in caplog.records[0].message

    def test_device_shake_logs_warning_with_ios_hint(self, caplog):
        d = MagicMock()
        d.capabilities = {"platformName": "Android"}
        d.shake.side_effect = Exception("not supported")
        device = DeviceActions(d)

        with caplog.at_level(logging.WARNING, logger="mobius.utils.device"):
            device.shake()

        assert len(caplog.records) == 1
        assert "iOS-only" in caplog.records[0].message

    def test_alerts_accept_logs_warning_when_both_paths_fail(self, caplog):
        d = MagicMock()
        d.switch_to.alert.accept.side_effect = Exception("no alert")
        d.execute_script.side_effect = Exception("mobile command unsupported")
        alerts = SystemAlertHandler(d)

        with caplog.at_level(logging.WARNING, logger="mobius.utils.alerts"):
            alerts.accept()

        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) == 1
        assert "both" in warning_records[0].message

    def test_network_apply_logs_warning_explaining_emulator_limitation(self, caplog):
        d = MagicMock()
        d.execute_script.side_effect = Exception("not implemented")
        net = NetworkSimulator(d)
        from mobius.utils.network import PROFILES, NetworkProfile

        with caplog.at_level(logging.WARNING, logger="mobius.utils.network"):
            net._apply(PROFILES[NetworkProfile.LTE])

        assert len(caplog.records) == 1
        assert "setNetworkSpeed" in caplog.records[0].message

    def test_clipboard_get_text_logs_warning(self, caplog):
        d = MagicMock()
        d.get_clipboard_text.side_effect = Exception("clipboard access denied")
        cb = ClipboardManager(d)

        with caplog.at_level(logging.WARNING, logger="mobius.utils.clipboard"):
            result = cb.get_text()

        assert result == ""
        assert len(caplog.records) == 1
        assert "get_text" in caplog.records[0].message

    def test_file_transfer_push_file_logs_warning_with_paths(self, caplog):
        ft = FileTransfer(MagicMock())

        with caplog.at_level(logging.WARNING, logger="mobius.utils.file_transfer"):
            result = ft.push_file("/nonexistent/local.txt", "/sdcard/remote.txt")

        assert result is False
        assert len(caplog.records) == 1
        assert "/nonexistent/local.txt" in caplog.records[0].message
        assert "/sdcard/remote.txt" in caplog.records[0].message

    def test_biometrics_send_match_logs_warning_on_unknown_platform(self, caplog):
        d = MagicMock()
        d.capabilities = {"platformName": "Windows"}
        bio = BiometricSimulator(d)

        with caplog.at_level(logging.WARNING, logger="mobius.utils.biometrics"):
            result = bio.send_match()

        assert result is False
        assert len(caplog.records) == 1
        assert "platform" in caplog.records[0].message.lower()


@pytest.mark.unit
class TestExpectedOutcomesLogDebugNotWarning:
    """
    Обратная проверка: НОРМАЛЬНЫЕ негативные исходы (элемент не найден,
    Appium не запущен) должны идти в DEBUG, а не WARNING — иначе любой
    здоровый прогон тестов завалит CI логи ложными предупреждениями.
    """

    def test_is_displayed_missing_element_is_debug_not_warning(self, caplog):
        d = MagicMock()
        elem = MobileElement(d, ("id", "missing"))

        with caplog.at_level(logging.DEBUG, logger="mobius.elements.mobile_element"):
            with pytest.MonkeyPatch().context() as mp:
                mp.setattr(elem, "_find", MagicMock(side_effect=Exception("not found")))
                result = elem.is_displayed

        assert result is False
        warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_records) == 0, "is_displayed=False should not log at WARNING level"

    def test_is_appium_available_false_is_debug_not_warning(self, caplog):
        from mobius.driver.appium_driver import is_appium_available

        with caplog.at_level(logging.DEBUG, logger="mobius.driver.appium_driver"):
            result = is_appium_available("http://localhost:1")

        assert result is False
        warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_records) == 0, (
            "Appium not running is the NORMAL case for unit-only CI runs — must not spam WARNING"
        )

    def test_platform_info_failure_is_debug_not_warning(self, caplog):
        from mobius.utils.platform_info import get_platform_name

        d = MagicMock()
        type(d).capabilities = property(lambda self: (_ for _ in ()).throw(Exception()))

        with caplog.at_level(logging.DEBUG, logger="mobius.utils.platform_info"):
            result = get_platform_name(d)

        assert result == ""
        warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_records) == 0
