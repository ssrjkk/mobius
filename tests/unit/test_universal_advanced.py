"""
Unit tests — advanced universal modules: webview, visual_regression,
file_transfer, device_logs, biometrics, interruptions, app_lifecycle,
screen_recording, app_config.

Все работают через generic mock driver — не завязаны на конкретный SUT,
как и остальной universal слой.
"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mobius.utils.app_config import AppConfig, ConfigDrivenScreen, LocatorSpec
from mobius.utils.app_lifecycle import AppInstaller
from mobius.utils.biometrics import BiometricSimulator, BiometricType
from mobius.utils.device_logs import CRASH_PATTERNS, CrashReport, DeviceLogCollector
from mobius.utils.file_transfer import FileTransfer
from mobius.utils.interruptions import InterruptionSimulator
from mobius.utils.screen_recording import ScreenRecorder
from mobius.utils.visual_regression import VisualDiffResult, VisualRegression
from mobius.utils.webview import NATIVE_CONTEXT, WebViewContext


def android_driver() -> MagicMock:
    d = MagicMock()
    d.capabilities = {"platformName": "Android", "appium:appPackage": "com.app"}
    return d


def ios_driver() -> MagicMock:
    d = MagicMock()
    d.capabilities = {"platformName": "iOS"}
    return d


# ── WebViewContext ─────────────────────────────────────────────────────────


@pytest.mark.unit
class TestWebViewContext:
    def setup_method(self):
        self.d = android_driver()
        self.wv = WebViewContext(self.d)

    def test_get_contexts(self):
        self.d.contexts = ["NATIVE_APP", "WEBVIEW_com.app"]
        assert self.wv.get_contexts() == ["NATIVE_APP", "WEBVIEW_com.app"]

    def test_get_contexts_exception_returns_native_only(self):
        type(self.d).contexts = property(lambda self: (_ for _ in ()).throw(Exception()))
        assert self.wv.get_contexts() == [NATIVE_CONTEXT]

    def test_get_current_context(self):
        self.d.context = "WEBVIEW_com.app"
        assert self.wv.get_current_context() == "WEBVIEW_com.app"

    def test_get_current_context_exception_returns_native(self):
        type(self.d).context = property(lambda self: (_ for _ in ()).throw(Exception()))
        assert self.wv.get_current_context() == NATIVE_CONTEXT

    def test_has_webview_true(self):
        self.d.contexts = ["NATIVE_APP", "WEBVIEW_1"]
        assert self.wv.has_webview() is True

    def test_has_webview_false(self):
        self.d.contexts = ["NATIVE_APP"]
        assert self.wv.has_webview() is False

    def test_switch_to_webview_by_name(self):
        self.d.contexts = ["NATIVE_APP", "WEBVIEW_checkout"]
        result = self.wv.switch_to_webview("WEBVIEW_checkout")
        assert result is True
        self.d.switch_to.context.assert_called_once_with("WEBVIEW_checkout")

    def test_switch_to_webview_auto_picks_first(self):
        self.d.contexts = ["NATIVE_APP", "WEBVIEW_1", "WEBVIEW_2"]
        result = self.wv.switch_to_webview()
        assert result is True
        self.d.switch_to.context.assert_called_once_with("WEBVIEW_1")

    def test_switch_to_webview_no_webview_available(self):
        self.d.contexts = ["NATIVE_APP"]
        assert self.wv.switch_to_webview() is False

    def test_switch_to_webview_name_not_found(self):
        self.d.contexts = ["NATIVE_APP", "WEBVIEW_1"]
        assert self.wv.switch_to_webview("WEBVIEW_nonexistent") is False

    def test_switch_to_webview_exception_returns_false(self):
        self.d.contexts = ["NATIVE_APP", "WEBVIEW_1"]
        self.d.switch_to.context.side_effect = Exception("switch failed")
        assert self.wv.switch_to_webview() is False

    def test_switch_to_native(self):
        result = self.wv.switch_to_native()
        assert result is True
        self.d.switch_to.context.assert_called_once_with(NATIVE_CONTEXT)

    def test_switch_to_native_exception_returns_false(self):
        self.d.switch_to.context.side_effect = Exception()
        assert self.wv.switch_to_native() is False

    def test_wait_for_webview_appears_immediately(self):
        self.d.contexts = ["NATIVE_APP", "WEBVIEW_1"]
        assert self.wv.wait_for_webview(timeout=1) is True

    def test_wait_for_webview_timeout(self):
        self.d.contexts = ["NATIVE_APP"]
        assert self.wv.wait_for_webview(timeout=1, poll_frequency=0.1) is False

    def test_in_webview_context_manager_switches_and_restores(self):
        self.d.contexts = ["NATIVE_APP", "WEBVIEW_1"]
        with self.wv.in_webview() as switched:
            assert switched is True
        calls = [c.args[0] for c in self.d.switch_to.context.call_args_list]
        assert calls == ["WEBVIEW_1", NATIVE_CONTEXT]

    def test_in_webview_restores_native_even_on_exception(self):
        self.d.contexts = ["NATIVE_APP", "WEBVIEW_1"]
        with pytest.raises(ValueError):
            with self.wv.in_webview():
                raise ValueError("test error inside webview block")
        last_call = self.d.switch_to.context.call_args_list[-1]
        assert last_call.args[0] == NATIVE_CONTEXT

    def test_get_page_source_in_webview(self):
        self.d.contexts = ["NATIVE_APP", "WEBVIEW_1"]
        self.d.page_source = "<html>test</html>"
        result = self.wv.get_page_source_in_webview()
        assert result == "<html>test</html>"

    def test_get_page_source_no_webview_returns_empty(self):
        self.d.contexts = ["NATIVE_APP"]
        result = self.wv.get_page_source_in_webview()
        assert result == ""


# ── VisualRegression ─────────────────────────────────────────────────────────


@pytest.mark.unit
class TestVisualRegression:
    def _make_screenshot_b64(self, color=(100, 150, 200), size=(50, 50)) -> str:
        from PIL import Image

        img = Image.new("RGB", size, color=color)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    def test_first_run_creates_baseline(self, tmp_path):
        d = MagicMock()
        d.get_screenshot_as_base64.return_value = self._make_screenshot_b64()
        vr = VisualRegression(
            d,
            baseline_dir=str(tmp_path / "baseline"),
            diff_dir=str(tmp_path / "diff"),
        )
        result = vr.compare("login_screen")
        assert result.match is True
        assert "first run" in result.reason

    def test_identical_screenshot_matches(self, tmp_path):
        d = MagicMock()
        d.get_screenshot_as_base64.return_value = self._make_screenshot_b64()
        vr = VisualRegression(d, baseline_dir=str(tmp_path / "b"), diff_dir=str(tmp_path / "d"))
        vr.compare("screen1")  # creates baseline
        result = vr.compare("screen1")  # compares against itself
        assert result.match is True
        assert result.diff_percentage == 0.0

    def test_different_screenshot_mismatches(self, tmp_path):
        d = MagicMock()
        d.get_screenshot_as_base64.return_value = self._make_screenshot_b64(color=(0, 0, 0))
        vr = VisualRegression(
            d,
            baseline_dir=str(tmp_path / "b"),
            diff_dir=str(tmp_path / "d"),
            threshold_pct=0.1,
        )
        vr.compare("screen2")  # black baseline

        d.get_screenshot_as_base64.return_value = self._make_screenshot_b64(color=(255, 255, 255))
        result = vr.compare("screen2")  # white — completely different
        assert result.match is False
        assert result.diff_percentage == 100.0  # каждый пиксель изменился

    def test_partial_diff_percentage_reflects_changed_area(self, tmp_path):
        """
        Проверяем формулу на промежуточном случае — не 0% и не 100%.
        Половина изображения (25х50 из 50х50) отличается → ожидаем ~50%.
        """
        from PIL import Image

        baseline_img = Image.new("RGB", (50, 50), color=(0, 0, 0))
        buf = io.BytesIO()
        baseline_img.save(buf, format="PNG")
        d = MagicMock()
        d.get_screenshot_as_base64.return_value = base64.b64encode(buf.getvalue()).decode()

        vr = VisualRegression(
            d,
            baseline_dir=str(tmp_path / "b"),
            diff_dir=str(tmp_path / "d"),
            threshold_pct=0.1,
        )
        vr.compare("half_diff")

        actual_img = Image.new("RGB", (50, 50), color=(0, 0, 0))
        for x in range(25, 50):
            for y in range(50):
                actual_img.putpixel((x, y), (255, 255, 255))
        buf2 = io.BytesIO()
        actual_img.save(buf2, format="PNG")
        d.get_screenshot_as_base64.return_value = base64.b64encode(buf2.getvalue()).decode()

        result = vr.compare("half_diff")
        assert result.match is False
        assert 45 <= result.diff_percentage <= 55, (
            f"Expected ~50% diff for half-changed image, got {result.diff_percentage}%"
        )

    def test_size_mismatch_detected(self, tmp_path):
        d = MagicMock()
        d.get_screenshot_as_base64.return_value = self._make_screenshot_b64(size=(50, 50))
        vr = VisualRegression(d, baseline_dir=str(tmp_path / "b"), diff_dir=str(tmp_path / "d"))
        vr.compare("screen3")

        d.get_screenshot_as_base64.return_value = self._make_screenshot_b64(size=(100, 100))
        result = vr.compare("screen3")
        assert result.match is False
        assert "size mismatch" in result.reason

    def test_update_baseline(self, tmp_path):
        d = MagicMock()
        d.get_screenshot_as_base64.return_value = self._make_screenshot_b64(color=(1, 1, 1))
        vr = VisualRegression(d, baseline_dir=str(tmp_path / "b"), diff_dir=str(tmp_path / "d"))
        vr.compare("screen4")

        d.get_screenshot_as_base64.return_value = self._make_screenshot_b64(color=(200, 200, 200))
        vr.update_baseline("screen4")
        result = vr.compare("screen4")
        assert result.match is True

    def test_assert_matches_raises_on_mismatch(self, tmp_path):
        d = MagicMock()
        d.get_screenshot_as_base64.return_value = self._make_screenshot_b64(color=(0, 0, 0))
        vr = VisualRegression(
            d,
            baseline_dir=str(tmp_path / "b"),
            diff_dir=str(tmp_path / "d"),
            threshold_pct=0.1,
        )
        vr.compare("screen5")

        d.get_screenshot_as_base64.return_value = self._make_screenshot_b64(color=(255, 255, 255))
        with pytest.raises(AssertionError, match="Visual regression"):
            vr.assert_matches("screen5")

    def test_assert_matches_passes_on_match(self, tmp_path):
        d = MagicMock()
        d.get_screenshot_as_base64.return_value = self._make_screenshot_b64()
        vr = VisualRegression(d, baseline_dir=str(tmp_path / "b"), diff_dir=str(tmp_path / "d"))
        vr.compare("screen6")
        vr.assert_matches("screen6")  # не падает — идентичный скриншот

    def test_diff_result_summary_match(self):
        r = VisualDiffResult(match=True, diff_percentage=0.0, baseline_path="a", actual_path="b")
        assert "MATCH" in r.summary()

    def test_diff_result_summary_mismatch(self):
        r = VisualDiffResult(match=False, diff_percentage=15.5, baseline_path="a", actual_path="b")
        assert "MISMATCH" in r.summary()
        assert "15.5" in r.summary()

    def test_diff_result_summary_skipped(self):
        r = VisualDiffResult(
            match=True,
            diff_percentage=0,
            baseline_path="a",
            actual_path="b",
            reason="baseline created (first run)",
        )
        assert "skipped" in r.summary()


# ── FileTransfer ─────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestFileTransfer:
    def setup_method(self):
        self.d = MagicMock()
        self.ft = FileTransfer(self.d)

    def test_push_file_reads_and_encodes(self, tmp_path):
        local = tmp_path / "test.txt"
        local.write_bytes(b"hello world")
        result = self.ft.push_file(str(local), "/sdcard/test.txt")
        assert result is True
        self.d.push_file.assert_called_once()
        call_kwargs = self.d.push_file.call_args
        assert call_kwargs[0][0] == "/sdcard/test.txt"

    def test_push_file_missing_local_returns_false(self):
        result = self.ft.push_file("/nonexistent/path.txt", "/sdcard/x.txt")
        assert result is False

    def test_push_test_image_generates_and_pushes(self):
        result = self.ft.push_test_image("/sdcard/test.png", width=10, height=10)
        assert result is True
        self.d.push_file.assert_called_once()

    def test_push_test_image_exception_returns_false(self):
        self.d.push_file.side_effect = Exception("device full")
        result = self.ft.push_test_image("/sdcard/test.png")
        assert result is False

    def test_pull_file_writes_local(self, tmp_path):
        content = b"pulled content"
        self.d.pull_file.return_value = base64.b64encode(content).decode()
        local = tmp_path / "pulled.txt"
        result = self.ft.pull_file("/sdcard/x.txt", str(local))
        assert result is True
        assert local.read_bytes() == content

    def test_pull_file_exception_returns_false(self, tmp_path):
        self.d.pull_file.side_effect = Exception("not found")
        result = self.ft.pull_file("/sdcard/missing.txt", str(tmp_path / "out.txt"))
        assert result is False

    def test_pull_folder_extracts_zip(self, tmp_path):
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("file1.txt", "content1")
        self.d.pull_folder.return_value = base64.b64encode(buf.getvalue()).decode()

        out_dir = tmp_path / "extracted"
        result = self.ft.pull_folder("/sdcard/folder", str(out_dir))
        assert result is True
        assert (out_dir / "file1.txt").read_text() == "content1"

    def test_pull_folder_exception_returns_false(self, tmp_path):
        self.d.pull_folder.side_effect = Exception("no such folder")
        result = self.ft.pull_folder("/sdcard/x", str(tmp_path))
        assert result is False

    def test_file_exists_on_device_true(self):
        self.d.pull_file.return_value = base64.b64encode(b"data").decode()
        assert self.ft.file_exists_on_device("/sdcard/exists.txt") is True

    def test_file_exists_on_device_false(self):
        self.d.pull_file.side_effect = Exception("not found")
        assert self.ft.file_exists_on_device("/sdcard/missing.txt") is False


# ── DeviceLogCollector ───────────────────────────────────────────────────────


@pytest.mark.unit
class TestDeviceLogCollector:
    def setup_method(self):
        self.d = MagicMock()
        self.logs = DeviceLogCollector(self.d)

    def test_get_available_log_types(self):
        self.d.log_types = ["logcat", "bugreport"]
        assert self.logs.get_available_log_types() == ["logcat", "bugreport"]

    def test_get_available_log_types_exception_returns_empty(self):
        type(self.d).log_types = property(lambda self: (_ for _ in ()).throw(Exception()))
        assert self.logs.get_available_log_types() == []

    def test_get_logs(self):
        self.d.get_log.return_value = [{"message": "test log", "level": "INFO"}]
        result = self.logs.get_logs("logcat")
        assert len(result) == 1

    def test_get_logs_exception_returns_empty(self):
        self.d.get_log.side_effect = Exception("no logs")
        assert self.logs.get_logs() == []

    def test_get_logs_text(self):
        self.d.get_log.return_value = [{"message": "line1"}, {"message": "line2"}]
        assert self.logs.get_logs_text() == ["line1", "line2"]

    def test_check_for_crash_detects_fatal_exception(self):
        self.d.get_log.return_value = [
            {"message": "Normal log line"},
            {"message": "FATAL EXCEPTION: main"},
        ]
        report = self.logs.check_for_crash()
        assert report.crashed is True
        assert len(report.matched_lines) == 1

    def test_check_for_crash_no_crash(self):
        self.d.get_log.return_value = [{"message": "Everything is fine"}]
        report = self.logs.check_for_crash()
        assert report.crashed is False

    def test_check_for_crash_filters_by_package(self):
        self.d.get_log.return_value = [
            {"message": "com.other.app: FATAL EXCEPTION"},
            {"message": "com.myapp: normal operation"},
        ]
        report = self.logs.check_for_crash(app_package="com.myapp")
        assert report.crashed is False

    def test_check_for_crash_anr_pattern(self):
        self.d.get_log.return_value = [{"message": "ANR in com.app.MainActivity"}]
        report = self.logs.check_for_crash()
        assert report.crashed is True

    def test_assert_no_crash_passes(self):
        self.d.get_log.return_value = [{"message": "all good"}]
        self.logs.assert_no_crash()  # не падает

    def test_assert_no_crash_raises(self):
        self.d.get_log.return_value = [{"message": "FATAL EXCEPTION: crash"}]
        with pytest.raises(AssertionError, match="CRASH DETECTED"):
            self.logs.assert_no_crash()

    def test_find_errors_filters_by_level(self):
        self.d.get_log.return_value = [
            {"message": "err1", "level": "ERROR"},
            {"message": "info1", "level": "INFO"},
            {"message": "err2", "level": "error"},
        ]
        errors = self.logs.find_errors()
        assert errors == ["err1", "err2"]

    def test_crash_report_summary_no_crash(self):
        r = CrashReport(crashed=False)
        assert "No crash" in r.summary()

    def test_crash_report_summary_with_crash(self):
        r = CrashReport(crashed=True, matched_lines=["FATAL EXCEPTION: x"])
        assert "CRASH DETECTED" in r.summary()

    def test_crash_patterns_not_empty(self):
        assert len(CRASH_PATTERNS) > 0


# ── BiometricSimulator ───────────────────────────────────────────────────────


@pytest.mark.unit
class TestBiometricSimulator:
    def test_is_enrolled_true(self):
        d = ios_driver()
        d.execute_script.return_value = True
        bio = BiometricSimulator(d)
        assert bio.is_enrolled() is True

    def test_is_enrolled_exception_returns_false(self):
        d = ios_driver()
        d.execute_script.side_effect = Exception("not simulator")
        bio = BiometricSimulator(d)
        assert bio.is_enrolled() is False

    def test_enroll_success(self):
        d = ios_driver()
        bio = BiometricSimulator(d)
        assert bio.enroll(True) is True
        d.execute_script.assert_called_once_with("mobile: enrollBiometric", {"isEnabled": True})

    def test_enroll_exception_returns_false(self):
        d = ios_driver()
        d.execute_script.side_effect = Exception()
        bio = BiometricSimulator(d)
        assert bio.enroll() is False

    def test_send_match_ios_uses_face_id_command(self):
        d = ios_driver()
        bio = BiometricSimulator(d)
        result = bio.send_match(True)
        assert result is True
        args = d.execute_script.call_args[0]
        assert args[0] == "mobile: sendBiometricMatch"
        assert args[1]["match"] is True

    def test_send_match_android_uses_fingerprint_command(self):
        d = android_driver()
        bio = BiometricSimulator(d)
        result = bio.send_match(True)
        assert result is True
        args = d.execute_script.call_args[0]
        assert args[0] == "mobile: fingerprint"

    def test_send_match_unknown_platform_returns_false(self):
        d = MagicMock()
        d.capabilities = {"platformName": "Windows"}
        bio = BiometricSimulator(d)
        assert bio.send_match() is False

    def test_send_match_exception_returns_false(self):
        d = ios_driver()
        d.execute_script.side_effect = Exception("simulator only")
        bio = BiometricSimulator(d)
        assert bio.send_match() is False

    def test_simulate_success(self):
        d = ios_driver()
        bio = BiometricSimulator(d)
        assert bio.simulate_success() is True
        assert d.execute_script.call_args[0][1]["match"] is True

    def test_simulate_failure(self):
        d = ios_driver()
        bio = BiometricSimulator(d)
        assert bio.simulate_failure() is True
        assert d.execute_script.call_args[0][1]["match"] is False

    def test_biometric_types_defined(self):
        assert BiometricType.FACE_ID.value == "faceId"
        assert BiometricType.FINGERPRINT.value == "fingerprint"


# ── InterruptionSimulator ────────────────────────────────────────────────────


@pytest.mark.unit
class TestInterruptionSimulator:
    def setup_method(self):
        self.d = android_driver()
        self.interrupt = InterruptionSimulator(self.d)

    def test_incoming_call(self):
        result = self.interrupt.incoming_call("5559999999")
        assert result is True
        args = self.d.execute_script.call_args[0]
        assert args[0] == "mobile: shell"
        assert "5559999999" in " ".join(args[1]["args"])

    def test_end_call(self):
        result = self.interrupt.end_call()
        assert result is True

    def test_incoming_sms(self):
        result = self.interrupt.incoming_sms("5551111111", "Hello")
        assert result is True

    def test_set_battery_level_clamps_upper(self):
        self.interrupt.set_battery_level(150)
        args = self.d.execute_script.call_args[0]
        assert "100" in " ".join(args[1]["args"])

    def test_set_battery_level_clamps_lower(self):
        self.interrupt.set_battery_level(-10)
        args = self.d.execute_script.call_args[0]
        assert "0" in " ".join(args[1]["args"])

    def test_set_battery_status_charging(self):
        result = self.interrupt.set_battery_status_charging(True)
        assert result is True
        args = self.d.execute_script.call_args[0]
        assert "charging" in " ".join(args[1]["args"])

    def test_set_battery_status_discharging(self):
        self.interrupt.set_battery_status_charging(False)
        args = self.d.execute_script.call_args[0]
        assert "discharging" in " ".join(args[1]["args"])

    def test_simulate_low_memory(self):
        result = self.interrupt.simulate_low_memory()
        assert result is True

    def test_simulate_low_memory_no_package_returns_false(self):
        d = MagicMock()
        d.capabilities = {"platformName": "Android"}  # no appPackage
        interrupt = InterruptionSimulator(d)
        assert interrupt.simulate_low_memory() is False

    def test_shell_exception_returns_false(self):
        self.d.execute_script.side_effect = Exception("emulator only")
        assert self.interrupt.incoming_call() is False


# ── AppInstaller ─────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestAppInstaller:
    def setup_method(self):
        self.d = MagicMock()
        self.installer = AppInstaller(self.d)

    def test_install_success(self):
        assert self.installer.install("/path/app.apk") is True
        self.d.install_app.assert_called_once_with("/path/app.apk")

    def test_install_exception_returns_false(self):
        self.d.install_app.side_effect = Exception("invalid apk")
        assert self.installer.install("/bad/path.apk") is False

    def test_uninstall_success(self):
        assert self.installer.uninstall("com.app") is True

    def test_uninstall_exception_returns_false(self):
        self.d.remove_app.side_effect = Exception("not installed")
        assert self.installer.uninstall("com.app") is False

    def test_is_installed_true(self):
        self.d.is_app_installed.return_value = True
        assert self.installer.is_installed("com.app") is True

    def test_is_installed_exception_returns_false(self):
        self.d.is_app_installed.side_effect = Exception()
        assert self.installer.is_installed("com.app") is False

    def test_update_calls_install_with_replace(self):
        result = self.installer.update("com.app", "/path/v2.apk")
        assert result is True
        self.d.install_app.assert_called_once_with("/path/v2.apk", replace=True)

    def test_update_exception_returns_false(self):
        self.d.install_app.side_effect = Exception("update failed")
        assert self.installer.update("com.app", "/path/v2.apk") is False

    def test_clean_install_when_already_installed(self):
        self.d.is_app_installed.return_value = True
        result = self.installer.clean_install("com.app", "/path/app.apk")
        assert result is True
        self.d.remove_app.assert_called_once_with("com.app")
        self.d.install_app.assert_called_once_with("/path/app.apk")

    def test_clean_install_when_not_installed(self):
        self.d.is_app_installed.return_value = False
        result = self.installer.clean_install("com.app", "/path/app.apk")
        assert result is True
        self.d.remove_app.assert_not_called()

    def test_clean_install_uninstall_fails_stops(self):
        self.d.is_app_installed.return_value = True
        self.d.remove_app.side_effect = Exception("stuck")
        result = self.installer.clean_install("com.app", "/path/app.apk")
        assert result is False
        self.d.install_app.assert_not_called()

    def test_get_app_strings_default(self):
        self.d.app_strings.return_value = {"key1": "value1"}
        result = self.installer.get_app_strings()
        assert result == {"key1": "value1"}

    def test_get_app_strings_with_language(self):
        self.d.app_strings.return_value = {"key1": "значение1"}
        result = self.installer.get_app_strings("ru")
        assert result == {"key1": "значение1"}
        self.d.app_strings.assert_called_once_with("ru")

    def test_get_app_strings_exception_returns_empty(self):
        self.d.app_strings.side_effect = Exception("not supported")
        assert self.installer.get_app_strings() == {}


# ── ScreenRecorder ───────────────────────────────────────────────────────────


@pytest.mark.unit
class TestScreenRecorder:
    def test_start_success(self, tmp_path):
        d = MagicMock()
        rec = ScreenRecorder(d, output_dir=str(tmp_path))
        assert rec.start() is True
        assert rec.is_recording is True

    def test_start_twice_returns_false(self, tmp_path):
        d = MagicMock()
        rec = ScreenRecorder(d, output_dir=str(tmp_path))
        rec.start()
        assert rec.start() is False

    def test_start_exception_returns_false(self, tmp_path):
        d = MagicMock()
        d.start_recording_screen.side_effect = Exception("not supported")
        rec = ScreenRecorder(d, output_dir=str(tmp_path))
        assert rec.start() is False
        assert rec.is_recording is False

    def test_stop_and_save_writes_file(self, tmp_path):
        d = MagicMock()
        video_bytes = b"fake_mp4_content"
        d.stop_recording_screen.return_value = base64.b64encode(video_bytes).decode()
        rec = ScreenRecorder(d, output_dir=str(tmp_path))
        rec.start()
        path = rec.stop_and_save("test_video")
        assert path is not None
        assert Path(path).read_bytes() == video_bytes
        assert rec.is_recording is False

    def test_stop_and_save_bytes_response(self, tmp_path):
        d = MagicMock()
        video_bytes = b"fake_content"
        d.stop_recording_screen.return_value = base64.b64encode(video_bytes)  # bytes not str
        rec = ScreenRecorder(d, output_dir=str(tmp_path))
        rec.start()
        path = rec.stop_and_save("test2")
        assert path is not None

    def test_stop_and_save_not_recording_returns_none(self, tmp_path):
        d = MagicMock()
        rec = ScreenRecorder(d, output_dir=str(tmp_path))
        assert rec.stop_and_save("x") is None

    def test_stop_and_save_exception_returns_none(self, tmp_path):
        d = MagicMock()
        d.stop_recording_screen.side_effect = Exception("failed")
        rec = ScreenRecorder(d, output_dir=str(tmp_path))
        rec.start()
        assert rec.stop_and_save("x") is None
        assert rec.is_recording is False

    def test_discard(self, tmp_path):
        d = MagicMock()
        rec = ScreenRecorder(d, output_dir=str(tmp_path))
        rec.start()
        rec.discard()
        assert rec.is_recording is False
        d.stop_recording_screen.assert_called_once()

    def test_discard_when_not_recording_noop(self, tmp_path):
        d = MagicMock()
        rec = ScreenRecorder(d, output_dir=str(tmp_path))
        rec.discard()  # не падает
        d.stop_recording_screen.assert_not_called()

    def test_record_test_context_manager_saves_on_true(self, tmp_path):
        d = MagicMock()
        d.stop_recording_screen.return_value = base64.b64encode(b"video").decode()
        rec = ScreenRecorder(d, output_dir=str(tmp_path))
        with rec.record_test("my_test", save_on=True):
            pass
        assert (tmp_path / "my_test.mp4").exists()

    def test_record_test_context_manager_discards_on_false(self, tmp_path):
        d = MagicMock()
        rec = ScreenRecorder(d, output_dir=str(tmp_path))
        with rec.record_test("my_test2", save_on=False):
            pass
        assert not (tmp_path / "my_test2.mp4").exists()


# ── AppConfig / ConfigDrivenScreen ───────────────────────────────────────────


@pytest.mark.unit
class TestAppConfig:
    def test_from_dict_basic(self):
        config = AppConfig.from_dict(
            {
                "name": "test_app",
                "platform": "Android",
                "app_package": "com.test",
            }
        )
        assert config.name == "test_app"
        assert config.app_package == "com.test"

    def test_from_dict_with_locators(self):
        config = AppConfig.from_dict(
            {
                "name": "test_app",
                "locators": {
                    "login_btn": {"strategy": "accessibility_id", "value": "Login"},
                },
            }
        )
        by, value = config.get_locator("login_btn")
        assert value == "Login"

    def test_get_locator_missing_raises_keyerror(self):
        config = AppConfig.from_dict({"name": "test_app"})
        with pytest.raises(KeyError, match="not defined"):
            config.get_locator("nonexistent")

    def test_to_capabilities_android(self):
        config = AppConfig.from_dict(
            {
                "name": "test_app",
                "platform": "Android",
                "device_name": "Pixel 7",
                "app_package": "com.test",
            }
        )
        caps = config.to_capabilities()
        d = caps.to_dict()
        assert d["platformName"] == "Android"
        assert d["appium:automationName"] == "UiAutomator2"

    def test_to_capabilities_ios(self):
        config = AppConfig.from_dict(
            {
                "name": "test_app",
                "platform": "iOS",
                "bundle_id": "com.test.ios",
            }
        )
        caps = config.to_capabilities()
        d = caps.to_dict()
        assert d["platformName"] == "iOS"
        assert d["appium:automationName"] == "XCUITest"
        assert d["appium:bundleId"] == "com.test.ios"

    def test_to_capabilities_includes_extra(self):
        config = AppConfig.from_dict(
            {
                "name": "test_app",
                "extra_capabilities": {"appium:noReset": True},
            }
        )
        caps = config.to_capabilities()
        d = caps.to_dict()
        assert d["appium:noReset"] is True

    def test_load_from_json_file(self, tmp_path):
        config_data = {
            "name": "json_app",
            "app_package": "com.json.test",
        }
        json_path = tmp_path / "config.json"
        json_path.write_text(json.dumps(config_data))

        config = AppConfig.load(json_path)
        assert config.name == "json_app"
        assert config.app_package == "com.json.test"

    def test_load_from_yaml_file(self, tmp_path):
        yaml_content = """
name: yaml_app
platform: Android
app_package: com.yaml.test
locators:
  submit_btn:
    strategy: id
    value: com.app:id/submit
"""
        yaml_path = tmp_path / "config.yaml"
        yaml_path.write_text(yaml_content)

        config = AppConfig.load(yaml_path)
        assert config.name == "yaml_app"
        by, value = config.get_locator("submit_btn")
        assert value == "com.app:id/submit"

    def test_locator_spec_as_tuple_accessibility_id(self):
        spec = LocatorSpec(strategy="accessibility_id", value="Submit")
        from appium.webdriver.common.appiumby import AppiumBy

        by, value = spec.as_tuple()
        assert by == AppiumBy.ACCESSIBILITY_ID
        assert value == "Submit"

    def test_locator_spec_unknown_strategy_defaults_to_xpath(self):
        spec = LocatorSpec(strategy="unknown_strategy", value="//button")
        from appium.webdriver.common.appiumby import AppiumBy

        by, _ = spec.as_tuple()
        assert by == AppiumBy.XPATH


@pytest.mark.unit
class TestConfigDrivenScreen:
    def setup_method(self):
        self.d = MagicMock()
        self.config = AppConfig.from_dict(
            {
                "name": "test_app",
                "locators": {
                    "login_btn": {"strategy": "id", "value": "com.app:id/login"},
                    "username": {"strategy": "id", "value": "com.app:id/username"},
                },
            }
        )
        self.screen = ConfigDrivenScreen(self.d, self.config)

    def test_find_uses_config_locator(self):
        self.screen.find("login_btn")
        self.d.find_element.assert_called_once()

    def test_tap_clicks_element(self):
        mock_elem = MagicMock()
        self.d.find_element.return_value = mock_elem
        self.screen.tap("login_btn")
        mock_elem.click.assert_called_once()

    def test_type_text_clears_and_sends(self):
        mock_elem = MagicMock()
        self.d.find_element.return_value = mock_elem
        self.screen.type_text("username", "test_user")
        mock_elem.clear.assert_called_once()
        mock_elem.send_keys.assert_called_once_with("test_user")

    def test_get_text(self):
        mock_elem = MagicMock()
        mock_elem.text = "Welcome"
        self.d.find_element.return_value = mock_elem
        assert self.screen.get_text("username") == "Welcome"

    def test_is_present_true(self):
        with patch("mobius.utils.app_config.WebDriverWait") as W:
            W.return_value.until.return_value = MagicMock()
            assert self.screen.is_present("login_btn") is True

    def test_is_present_false(self):
        with patch("mobius.utils.app_config.WebDriverWait") as W:
            W.return_value.until.side_effect = Exception("not found")
            assert self.screen.is_present("login_btn") is False


@pytest.mark.unit
class TestRemainingBranches:
    """Точечные тесты на последние непокрытые ветки после первого прохода."""

    def test_app_config_yaml_import_error_raises_helpful_message(self, tmp_path):
        """app_config.py: PyYAML отсутствует → ImportError с понятным сообщением."""
        yaml_path = tmp_path / "config.yaml"
        yaml_path.write_text("name: test_app\n")

        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError("No module named 'yaml'")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=fake_import):
            with pytest.raises(ImportError, match="PyYAML не установлен"):
                AppConfig.load(yaml_path)

    def test_simulate_low_memory_execute_script_exception(self):
        """interruptions.py: execute_script падает → simulate_low_memory возвращает False."""
        d = android_driver()
        d.execute_script.side_effect = Exception("shell command failed")
        interrupt = InterruptionSimulator(d)
        assert interrupt.simulate_low_memory() is False

    def test_discard_swallows_stop_recording_exception(self, tmp_path):
        """screen_recording.py: discard() не падает если stop_recording_screen кидает исключение."""
        d = MagicMock()
        d.stop_recording_screen.side_effect = Exception("already stopped")
        rec = ScreenRecorder(d, output_dir=str(tmp_path))
        rec.start()
        rec.discard()  # не падает несмотря на исключение внутри
        assert rec.is_recording is False

    def test_get_page_source_in_webview_exception_returns_empty(self):
        """webview.py: page_source кидает исключение внутри webview → возвращаем ''."""
        d = android_driver()
        d.contexts = ["NATIVE_APP", "WEBVIEW_1"]
        type(d).page_source = property(lambda self: (_ for _ in ()).throw(Exception("detached")))
        wv = WebViewContext(d)
        result = wv.get_page_source_in_webview()
        assert result == ""


@pytest.mark.unit
class TestConfigDrivenGeneralization:
    """
    ADR-002 честно отмечал: 'проверено только на одном конфиге
    (sauce_labs_demo.yaml)'. Этот тест закрывает пробел — проверяет что
    механизм реально работает со СТРУКТУРНО другим приложением (iOS,
    другие locator strategies), не просто скопирован под один случай.
    """

    def test_ios_config_loads(self):
        config = AppConfig.load("apps/ios_reference_example.yaml")
        assert config.platform == "iOS"
        assert config.bundle_id == "com.example.ioshop"

    def test_ios_config_capabilities_use_xcuitest(self):
        config = AppConfig.load("apps/ios_reference_example.yaml")
        caps = config.to_capabilities()
        d = caps.to_dict()
        assert d["platformName"] == "iOS"
        assert d["appium:automationName"] == "XCUITest"
        assert d["appium:bundleId"] == "com.example.ioshop"

    def test_ios_config_extra_capabilities_present(self):
        config = AppConfig.load("apps/ios_reference_example.yaml")
        caps = config.to_capabilities()
        d = caps.to_dict()
        assert d["appium:autoAcceptAlerts"] is True

    def test_ios_predicate_strategy_resolves_correctly(self):
        config = AppConfig.load("apps/ios_reference_example.yaml")
        by, value = config.get_locator("login_button")
        assert by == "-ios predicate string"
        assert "Log In" in value

    def test_class_name_strategy_resolves_correctly(self):
        config = AppConfig.load("apps/ios_reference_example.yaml")
        by, value = config.get_locator("add_to_cart_button")
        assert by == "class name"
        assert value == "XCUIElementTypeButton"

    def test_two_different_configs_dont_interfere(self):
        """Загрузка одного конфига не должна влиять на состояние другого."""
        android_config = AppConfig.load("apps/sauce_labs_demo.yaml")
        ios_config = AppConfig.load("apps/ios_reference_example.yaml")

        assert android_config.platform == "Android"
        assert ios_config.platform == "iOS"
        assert android_config.get_locator("login_button") != ios_config.get_locator("login_button")
