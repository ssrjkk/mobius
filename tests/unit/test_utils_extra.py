"""Unit tests — deeplink, network, performance, accessibility, screenshot."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs

import pytest

from mobius.utils.accessibility import A11yReport, AccessibilityChecker
from mobius.utils.deeplink import DeepLink
from mobius.utils.network import PROFILES, NetworkCondition, NetworkProfile, NetworkSimulator
from mobius.utils.performance import PerformanceCollector
from mobius.utils.screenshot import ScreenshotUtils


def _element(
    tag: str,
    *,
    clickable: str = "false",
    content_desc: str = "Hello",
    resource_id: str = "txt",
    text: str = "Hello",
    width: int = 200,
    height: int = 40,
    displayed: bool = True,
) -> MagicMock:
    """WebElement-заглушка с читаемыми атрибутами для проверок доступности."""
    elem = MagicMock()
    elem.tag_name = tag
    elem.text = text
    elem.size = {"width": width, "height": height}
    elem.is_displayed.return_value = displayed
    attrs = {"clickable": clickable, "content-desc": content_desc, "resource-id": resource_id}
    elem.get_attribute.side_effect = lambda key: attrs.get(key, "")
    return elem


def _text_elem(**kwargs: Any) -> MagicMock:
    return _element("android.widget.TextView", **kwargs)


def _image_elem(**kwargs: Any) -> MagicMock:
    return _element("android.widget.ImageView", text="", content_desc="", **kwargs)


@pytest.mark.unit
class TestDeepLink:
    def setup_method(self):
        self.d = MagicMock()
        self.d.capabilities = {"appium:appPackage": "com.app"}
        self.dl = DeepLink(self.d, scheme="myapp")

    def test_build_url_no_params(self):
        assert self.dl.build_url("product/1") == "myapp://product/1"

    def test_build_url_with_params(self):
        url = self.dl.build_url("search", {"q": "shoes", "page": "1"})
        assert "myapp://search?" in url
        assert "q=shoes" in url

    def test_build_url_params_sorted(self):
        url = self.dl.build_url("x", {"b": "2", "a": "1"})
        assert url.index("a=1") < url.index("b=2")

    def test_query_value_cannot_forge_extra_params(self):
        url = self.dl.build_url("search", {"q": "shoes&free=true"})
        assert url == "myapp://search?q=shoes%26free%3Dtrue"

    def test_special_characters_survive_a_round_trip(self):
        params = {"q": "one two", "tag": "a=b", "path": "x/y", "page": 2}
        url = self.dl.build_url("search", params)
        assert parse_qs(url.split("?", 1)[1]) == {
            "q": ["one two"],
            "tag": ["a=b"],
            "path": ["x/y"],
            "page": ["2"],
        }

    def test_path_cannot_inject_a_query(self):
        url = self.dl.build_url("cart?page=2", {"ref": "ad"})
        assert url.count("?") == 1
        assert parse_qs(url.split("?", 1)[1]) == {"ref": ["ad"]}

    def test_open_calls_execute_script(self):
        self.dl.open("cart")
        self.d.execute_script.assert_called_once()

    def test_open_product(self):
        self.dl.open_product(42)
        args = self.d.execute_script.call_args[0]
        assert "product/42" in str(args)

    def test_open_cart(self):
        self.dl.open_cart()
        self.d.execute_script.assert_called_once()

    def test_open_login(self):
        self.dl.open_login()
        self.d.execute_script.assert_called_once()

    def test_open_with_params(self):
        self.dl.open("search", {"q": "boots"})
        self.d.execute_script.assert_called_once()


@pytest.mark.unit
class TestNetworkSimulator:
    def setup_method(self):
        self.d = MagicMock()
        self.n = NetworkSimulator(self.d)

    def test_go_offline(self):
        assert self.n.go_offline() is True
        self.d.set_network_connection.assert_called_once_with(0)
        assert self.n.current_profile == NetworkProfile.OFFLINE

    def test_go_offline_failure_does_not_mark_device_offline(self):
        """
        Профиль описывает состояние устройства, а не намерение теста: если
        команда не прошла, «offline» выставлен быть не может — иначе тест в
        offline крутится на полностью связном устройстве и зелёный ничего не
        проверяет.
        """
        self.d.set_network_connection.side_effect = Exception("no api")
        assert self.n.go_offline() is False
        assert self.n.current_profile is None

    def test_go_online(self):
        assert self.n.go_online() is True
        self.d.set_network_connection.assert_called_once_with(6)
        assert self.n.current_profile == NetworkProfile.WIFI

    def test_go_online_failure_does_not_mark_device_online(self):
        self.d.set_network_connection.side_effect = Exception("no api")
        assert self.n.go_online() is False
        assert self.n.current_profile is None

    def test_set_profile_lte(self):
        assert self.n.set_profile(NetworkProfile.LTE) is True
        assert self.n.current_profile == NetworkProfile.LTE
        args = self.d.execute_script.call_args[0]
        assert args[0] == "mobile: setNetworkSpeed"
        assert args[1] == {"download": 10_000, "upload": 5_000}

    def test_set_profile_wifi(self):
        assert self.n.set_profile(NetworkProfile.WIFI) is True
        assert self.n.current_profile == NetworkProfile.WIFI

    def test_set_profile_2g(self):
        assert self.n.set_profile(NetworkProfile.TWO_G) is True
        assert self.n.current_profile == NetworkProfile.TWO_G

    def test_set_profile_offline_calls_go_offline(self):
        self.n.set_profile(NetworkProfile.OFFLINE)
        self.d.set_network_connection.assert_called_once_with(0)
        assert self.n.current_profile == NetworkProfile.OFFLINE

    def test_set_profile_rejected_leaves_profile_untouched(self):
        self.d.execute_script.side_effect = Exception("not supported")
        assert self.n.set_profile(NetworkProfile.THREE_G) is False
        assert self.n.current_profile is None

    def test_set_profile_from_offline_restores_connectivity_first(self):
        """Любой профиль кроме OFFLINE означает связь: сначала online, потом скорость."""
        self.n.go_offline()
        assert self.n.set_profile(NetworkProfile.LTE) is True
        calls = [c[0][0] for c in self.d.set_network_connection.call_args_list]
        assert calls == [0, 6]
        assert self.n.current_profile == NetworkProfile.LTE

    def test_apply_exception_returns_false(self):
        self.d.execute_script.side_effect = Exception("not supported")
        assert self.n._apply(PROFILES[NetworkProfile.LTE]) is False

    def test_profiles_have_all_keys(self):
        for p in NetworkProfile:
            assert p in PROFILES
            assert isinstance(PROFILES[p], NetworkCondition)

    def test_wifi_fastest(self):
        wifi_speed = PROFILES[NetworkProfile.WIFI].download_speed
        two_g_speed = PROFILES[NetworkProfile.TWO_G].download_speed
        assert wifi_speed > two_g_speed

    def test_get_condition(self):
        c = NetworkSimulator.get_condition(NetworkProfile.THREE_G)
        assert c.latency == 100

    def test_initial_profile_none(self):
        n = NetworkSimulator(MagicMock())
        assert n.current_profile is None


@pytest.mark.unit
class TestPerformanceCollector:
    def setup_method(self):
        self.d = MagicMock()
        self.p = PerformanceCollector(self.d)

    def test_measure_records_metric(self):
        import time

        with self.p.measure("test_op"):
            time.sleep(0.01)
        assert "test_op" in self.p.report.metrics
        assert self.p.report.metrics["test_op"] > 0

    def test_report_add_get(self):
        self.p.report.add("my_metric", 123.4)
        assert self.p.report.get("my_metric") == 123.4

    def test_report_get_missing(self):
        assert self.p.report.get("missing") is None

    def test_assert_under_passes(self):
        self.p.report.add("fast_op", 50.0)
        self.p.report.assert_under("fast_op", 100.0)

    def test_assert_under_fails(self):
        self.p.report.add("slow_op", 600.0)
        with pytest.raises(AssertionError):
            self.p.report.assert_under("slow_op", 500.0)

    def test_assert_under_key_error(self):
        with pytest.raises(KeyError):
            self.p.report.assert_under("nonexistent", 100.0)

    def test_thresholds_defined(self):
        assert "app_startup" in PerformanceCollector.THRESHOLDS
        assert "tap_response" in PerformanceCollector.THRESHOLDS

    def test_summary_contains_metrics(self):
        self.p.report.add("startup", 1500.0)
        assert "startup" in self.p.report.summary()

    def test_measure_app_startup(self):
        ms = self.p.measure_app_startup("com.example.app")
        assert isinstance(ms, float)
        assert ms >= 0
        assert "app_startup" in self.p.report.metrics

    def test_measure_app_startup_terminate_exception(self):
        self.d.terminate_app.side_effect = Exception("not running")
        ms = self.p.measure_app_startup("com.app")
        assert ms >= 0

    def test_assert_all_thresholds_pass(self):
        self.p.report.add("tap_response", 50.0)
        self.p.assert_all_thresholds()

    def test_assert_all_thresholds_fail(self):
        self.p.report.add("tap_response", 9999.0)
        with pytest.raises(AssertionError):
            self.p.assert_all_thresholds()

    def test_frame_time_threshold_is_milliseconds(self):
        """Порог в ms, поэтому ключ не должен называться «fps»."""
        assert "frame_time" in PerformanceCollector.THRESHOLDS
        assert "scroll_fps" not in PerformanceCollector.THRESHOLDS

    def test_assert_all_thresholds_is_never_vacuously_green(self):
        self.p.report.add("some_custom_step", 5.0)
        with pytest.raises(AssertionError, match="without checking anything"):
            self.p.assert_all_thresholds()

    def test_unknown_metric_is_reported_but_does_not_fail(self):
        self.p.report.add("some_custom_step", 5.0)
        self.p.report.add("tap_response", 5.0)
        self.p.assert_all_thresholds()  # падает только если не проверено ничего


@pytest.mark.unit
class TestA11yReport:
    def test_add_violation(self):
        r = A11yReport()
        r.add_violation("btn_1", "Missing content-desc", "error")
        assert len(r.violations) == 1
        assert r.has_errors

    def test_add_pass(self):
        r = A11yReport()
        r.add_pass()
        r.add_pass()
        assert r.passed == 2

    def test_has_errors_false_when_only_warnings(self):
        r = A11yReport()
        r.add_violation("x", "small target", "warning")
        assert not r.has_errors

    def test_has_violations_true(self):
        r = A11yReport()
        r.add_violation("x", "issue", "warning")
        assert r.has_violations

    def test_summary_contains_violation(self):
        r = A11yReport()
        r.add_violation("btn", "Missing label", "error")
        assert "btn" in r.summary()


@pytest.mark.unit
class TestAccessibilityChecker:
    def test_assert_no_errors_passes(self):
        checker = AccessibilityChecker(MagicMock())
        report = A11yReport()
        report.add_pass()
        checker.assert_no_errors(report)

    def test_assert_no_errors_raises(self):
        checker = AccessibilityChecker(MagicMock())
        report = A11yReport()
        report.add_violation("btn", "Missing content-desc", "error")
        with pytest.raises(AssertionError, match="Accessibility errors"):
            checker.assert_no_errors(report)

    def test_assert_no_errors_ignores_warnings(self):
        checker = AccessibilityChecker(MagicMock())
        report = A11yReport()
        report.add_violation("btn", "small", "warning")
        checker.assert_no_errors(report)

    def test_check_screen_catches_element_exception(self):
        d = MagicMock()
        bad_elem = MagicMock()
        bad_elem.get_attribute.side_effect = Exception("stale")
        d.find_elements.return_value = [bad_elem]
        checker = AccessibilityChecker(d)
        report = checker.check_screen()
        assert isinstance(report, A11yReport)

    def test_check_screen_passes_good_elements(self):
        d = MagicMock()
        elem = MagicMock()
        elem.tag_name = "android.widget.Button"
        elem.get_attribute.side_effect = lambda k: {
            "clickable": "true",
            "content-desc": "Login",
            "resource-id": "btn_login",
        }.get(k, "")
        elem.text = ""
        elem.is_displayed.return_value = True
        elem.size = {"width": 100, "height": 100}
        d.find_elements.return_value = [elem]
        checker = AccessibilityChecker(d)
        report = checker.check_screen()
        assert report.passed > 0

    def test_check_element_small_touch_target(self):
        checker = AccessibilityChecker(MagicMock(), density_factor=1.0)
        elem = MagicMock()
        elem.tag_name = "android.widget.Button"
        elem.get_attribute.side_effect = lambda k: {
            "clickable": "true",
            "content-desc": "OK",
            "resource-id": "btn",
        }.get(k, "")
        elem.text = "OK"
        elem.is_displayed.return_value = True
        elem.size = {"width": 20, "height": 20}
        report = checker.check_element(elem)
        assert any("small" in v.issue for v in report.violations)

    def test_check_element_missing_content_desc_error(self):
        checker = AccessibilityChecker(MagicMock(), density_factor=1.0)
        report = checker.check_element(_image_elem())
        assert any(v.severity == "error" for v in report.violations)

    def test_check_element_image_missing_alt(self):
        checker = AccessibilityChecker(MagicMock(), density_factor=1.0)
        elem = _image_elem(clickable="false", resource_id="img_hero")
        report = checker.check_element(elem)
        assert any("Image" in v.issue for v in report.violations)

    def test_check_element_non_clickable_passes(self):
        checker = AccessibilityChecker(MagicMock(), density_factor=1.0)
        report = checker.check_element(_text_elem())
        assert report.passed == 1
        assert report.violations == []

    def test_check_element_large_touch_target_ok(self):
        checker = AccessibilityChecker(MagicMock(), density_factor=1.0)
        elem = _text_elem(clickable="true", resource_id="btn_submit", width=200, height=100)
        report = checker.check_element(elem)
        assert [v for v in report.violations if "small" in v.issue] == []

    def test_clean_element_with_small_target_is_not_counted_as_passed(self):
        """Один элемент — одна строка отчёта: зачёт и нарушение одновременно недопустимы."""
        checker = AccessibilityChecker(MagicMock(), density_factor=1.0)
        elem = _text_elem(
            clickable="true", content_desc="Submit", resource_id="btn", width=10, height=10
        )
        report = checker.check_element(elem)
        assert report.elements_checked == 1
        assert report.passed == 0
        assert len(report.violations) == 1

    def test_stale_elements_are_out_of_the_counts(self):
        d = MagicMock()
        bad = MagicMock()
        bad.get_attribute.side_effect = Exception("stale")
        d.find_elements.return_value = [bad, _text_elem()]
        checker = AccessibilityChecker(d, density_factor=1.0)
        report = checker.check_screen()
        assert report.elements_checked == 1
        assert report.passed == 1

    def test_touch_target_is_pixels_times_density_not_raw_pixels(self):
        """100x100px на 420dpi — это 38dp: слишком мелко, хотя число больше 44."""
        elem = _text_elem(clickable="true", content_desc="Buy", width=100, height=100)

        dense = AccessibilityChecker(MagicMock(), density_factor=2.625).check_element(elem)
        mdpi = AccessibilityChecker(MagicMock(), density_factor=1.0).check_element(elem)

        assert any("small" in v.issue for v in dense.violations)
        assert any("small" in v.issue for v in mdpi.violations) is False

    def test_density_comes_from_the_device_and_is_cached(self):
        d = MagicMock()
        d.execute_script.return_value = {"stdout": "Physical density: 420", "stderr": ""}
        checker = AccessibilityChecker(d)
        elem = _text_elem(clickable="true", content_desc="Buy", width=100, height=100)

        assert any("small" in v.issue for v in checker.check_element(elem).violations)
        checker.check_element(elem)
        assert d.execute_script.call_count == 1

    def test_override_density_wins_over_physical(self):
        d = MagicMock()
        d.execute_script.return_value = "Physical density: 420\nOverride density: 160\n"
        checker = AccessibilityChecker(d)
        elem = _text_elem(clickable="true", content_desc="Buy", width=50, height=50)
        assert checker.check_element(elem).passed == 1

    def test_no_density_disables_the_size_rule(self, caplog: pytest.LogCaptureFixture):
        d = MagicMock()
        d.execute_script.side_effect = Exception("mobile: shell not supported")
        checker = AccessibilityChecker(d)
        elem = _text_elem(clickable="true", content_desc="Buy", width=1, height=1)

        report = checker.check_element(elem)

        assert report.violations == []
        assert "density" in caplog.text.lower()

    def test_check_element_stale_element_returns_empty_report(self):
        """check_element: stale element во время проверки → пустой отчёт, не падает."""
        checker = AccessibilityChecker(MagicMock(), density_factor=1.0)
        elem = MagicMock()
        elem.tag_name = "android.widget.Button"
        elem.get_attribute.side_effect = Exception("stale element reference")
        report = checker.check_element(elem)
        assert report.violations == []
        assert report.passed == 0
        assert report.elements_checked == 0

    def test_clickable_without_content_desc_and_text_is_error(self):
        """Кликабельный элемент без text И без content-desc — error."""
        checker = AccessibilityChecker(MagicMock(), density_factor=1.0)
        elem = _element("android.widget.Button", clickable="true", content_desc="", text="")
        report = checker.check_element(elem)
        assert any(
            "missing content-desc" in v.issue and v.severity == "error"
            for v in report.violations
        )


@pytest.mark.unit
class TestScreenshotUtils:
    def setup_method(self):
        self.d = MagicMock()

    def test_take_saves_file(self, tmp_path):
        ss = ScreenshotUtils(self.d, str(tmp_path))
        path = ss.take("test")
        self.d.save_screenshot.assert_called_once()
        assert "test" in str(path)

    def test_take_no_name(self, tmp_path):
        ss = ScreenshotUtils(self.d, str(tmp_path))
        path = ss.take()
        assert "screenshot_" in str(path)

    def test_take_allure_returns_bytes(self, tmp_path):
        import base64

        self.d.get_screenshot_as_base64.return_value = base64.b64encode(b"png").decode()
        ss = ScreenshotUtils(self.d, str(tmp_path))
        result = ss.take_allure()
        assert isinstance(result, bytes)

    def test_attach_to_allure_calls_allure(self, tmp_path):
        self.d.get_screenshot_as_png.return_value = b"png"
        ss = ScreenshotUtils(self.d, str(tmp_path))
        import allure

        with patch.object(allure, "attach") as m:
            ss.attach_to_allure("test")
        m.assert_called_once()

    def test_attach_to_allure_fallback_on_error(self, tmp_path):
        self.d.get_screenshot_as_png.side_effect = Exception("no screen")
        ss = ScreenshotUtils(self.d, str(tmp_path))
        ss.attach_to_allure("fail")

    def test_attach_page_source(self, tmp_path):
        self.d.page_source = "<ui/>"
        ss = ScreenshotUtils(self.d, str(tmp_path))
        import allure

        with patch.object(allure, "attach") as m:
            ss.attach_page_source()
        m.assert_called_once()

    def test_attach_page_source_exception_swallowed(self, tmp_path):
        type(self.d).page_source = property(lambda self: (_ for _ in ()).throw(Exception()))
        ss = ScreenshotUtils(self.d, str(tmp_path))
        ss.attach_page_source()


@pytest.mark.unit
class TestAccessibilityCheckerFixes:
    """Тесты новых методов: max_elements limit, check_element, assert_no_violations."""

    def test_max_elements_limits_check(self):
        d = MagicMock()
        elems = [MagicMock() for _ in range(200)]
        for e in elems:
            e.tag_name = "android.widget.TextView"
            e.get_attribute.side_effect = lambda k: {
                "clickable": "false",
                "content-desc": "x",
                "resource-id": "y",
            }.get(k, "")
            e.text = "x"
            e.is_displayed.return_value = True
            e.size = {"width": 100, "height": 100}
        d.find_elements.return_value = elems
        checker = AccessibilityChecker(d, max_elements=50)
        report = checker.check_screen()
        assert report.elements_checked == 50

    def test_default_max_elements_is_100(self):
        checker = AccessibilityChecker(MagicMock())
        assert checker._max_elements == 100

    def test_check_screen_find_elements_exception(self):
        d = MagicMock()
        d.find_elements.side_effect = Exception("driver error")
        checker = AccessibilityChecker(d)
        report = checker.check_screen()
        assert report.elements_checked == 0

    def test_check_element_single(self):
        d = MagicMock()
        elem = MagicMock()
        elem.tag_name = "android.widget.Button"
        elem.get_attribute.side_effect = lambda k: {
            "clickable": "true",
            "content-desc": "OK",
            "resource-id": "btn",
        }.get(k, "")
        elem.text = ""
        elem.is_displayed.return_value = True
        elem.size = {"width": 100, "height": 100}
        checker = AccessibilityChecker(d)
        report = checker.check_element(elem)
        assert report.elements_checked == 1
        assert report.passed == 1

    def test_assert_no_violations_passes_when_clean(self):
        checker = AccessibilityChecker(MagicMock())
        report = A11yReport()
        report.add_pass()
        checker.assert_no_violations(report)  # не падает

    def test_assert_no_violations_raises_on_warning(self):
        checker = AccessibilityChecker(MagicMock())
        report = A11yReport()
        report.add_violation("btn", "small target", "warning")
        with pytest.raises(AssertionError, match="Accessibility violations"):
            checker.assert_no_violations(report)

    def test_summary_includes_elements_checked(self):
        report = A11yReport()
        report.elements_checked = 42
        report.add_pass()
        assert "42 checked" in report.summary()


@pytest.mark.unit
class TestDeepLinkPackageSafety:
    """Тесты безопасного получения appPackage."""

    def test_get_package_from_appium_key(self):
        d = MagicMock()
        d.capabilities = {"appium:appPackage": "com.app.test"}
        dl = DeepLink(d)
        assert dl._get_package() == "com.app.test"

    def test_get_package_fallback_key(self):
        d = MagicMock()
        d.capabilities = {"appPackage": "com.app.fallback"}
        dl = DeepLink(d)
        assert dl._get_package() == "com.app.fallback"

    def test_get_package_missing_returns_empty(self):
        d = MagicMock()
        d.capabilities = {}
        dl = DeepLink(d)
        assert dl._get_package() == ""

    def test_get_package_none_capabilities(self):
        d = MagicMock()
        d.capabilities = None
        dl = DeepLink(d)
        assert dl._get_package() == ""

    def test_get_package_exception_returns_empty(self):
        d = MagicMock()
        type(d).capabilities = property(lambda self: (_ for _ in ()).throw(Exception()))
        dl = DeepLink(d)
        assert dl._get_package() == ""

    def test_open_checkout(self):
        d = MagicMock()
        d.capabilities = {"appium:appPackage": "com.app"}
        dl = DeepLink(d)
        dl.open_checkout()
        d.execute_script.assert_called_once()

    def test_open_uses_get_package(self):
        d = MagicMock()
        d.capabilities = {"appium:appPackage": "com.app.real"}
        dl = DeepLink(d)
        dl.open("home")
        call_args = d.execute_script.call_args[0]
        assert call_args[1]["package"] == "com.app.real"


@pytest.mark.unit
class TestShellSafety:
    """
    Аргументы `mobile: shell` — внешние данные из конфигов и фикстур.
    Appium склеивает их в одну строку `adb shell`, а `mobile: shell emu`
    попадает в Telnet-консоль эмулятора, где `\n` = «началась новая
    команда». Передача списком поэтому не защита: проверка обязана
    стоять на входе.
    """

    def test_valid_package_passes_through(self):
        from mobius.utils.shell_safety import checked_package

        assert checked_package("com.example.app", caller="t") == "com.example.app"

    @pytest.mark.parametrize(
        "package",
        [
            "com.example.app; rm -rf /",
            "com.example.app && curl evil",
            "com.example.app|wc",
            "com.example.app\nsms send 5551234",
            "not-a-package",
            "1com.example.app",
            "com",
            "",
            "  ",
        ],
    )
    def test_package_that_is_not_a_package_is_refused(self, package):
        from mobius.utils.shell_safety import checked_package

        with pytest.raises(ValueError, match="valid Android package name"):
            checked_package(package, caller="t")

    @pytest.mark.parametrize("phone", ["5551234567", "+15551234567", "42"])
    def test_plain_phone_passes_through(self, phone):
        from mobius.utils.shell_safety import checked_phone

        assert checked_phone(phone, caller="t") == phone

    @pytest.mark.parametrize(
        "phone",
        [
            "5551234567\nsms send 1234",
            "5551234567 sms send 1234",
            "555-123-4567",
            "5551234567;",
            "+5551234567\r",
            "",
            "abc",
        ],
    )
    def test_phone_that_is_not_a_number_is_refused(self, phone):
        from mobius.utils.shell_safety import checked_phone

        with pytest.raises(ValueError, match="plain phone number"):
            checked_phone(phone, caller="t")

    def test_console_text_may_contain_spaces_and_punctuation(self):
        from mobius.utils.shell_safety import checked_console_text

        msg = "Order 42 is ready; call me back, ok?"
        assert checked_console_text(msg, caller="t") == msg

    @pytest.mark.parametrize("msg", ["hi\nsms send 5551234", "hi\rupdate exit", "hi\x00there"])
    def test_console_text_with_control_char_is_refused(self, msg):
        from mobius.utils.shell_safety import checked_console_text

        with pytest.raises(ValueError, match="control character"):
            checked_console_text(msg, caller="t")

    def test_error_message_names_the_caller(self):
        """Без caller непонятно какой хелпер отказал — это же и диагностика в CI."""
        from mobius.utils.shell_safety import checked_package

        with pytest.raises(ValueError, match="simulate_low_memory"):
            checked_package("bad name", caller="simulate_low_memory")


@pytest.mark.unit
class TestReadCapability:
    """
    `str(caps.get(k))` превращает MagicMock или dict в осмысленную на вид
    строку, и модуль начинает сообщать capability, которого нет. Проверка
    типа здесь — единственное, что отличает «задан» от «мусор на входе».
    """

    def test_reads_preferring_first_key(self):
        from mobius.utils.capability import read_capability

        d = MagicMock()
        d.capabilities = {"appium:appPackage": "com.first", "appPackage": "com.second"}
        assert read_capability(d, "appium:appPackage", "appPackage", caller="t") == "com.first"

    def test_falls_back_to_legacy_key(self):
        from mobius.utils.capability import read_capability

        d = MagicMock()
        d.capabilities = {"appPackage": "com.legacy"}
        assert read_capability(d, "appium:appPackage", "appPackage", caller="t") == "com.legacy"

    def test_strips_surrounding_whitespace(self):
        from mobius.utils.capability import read_capability

        d = MagicMock()
        d.capabilities = {"appium:app": "  /tmp/app.apk  "}
        assert read_capability(d, "appium:app", caller="t") == "/tmp/app.apk"

    def test_empty_value_is_skipped_not_returned(self):
        from mobius.utils.capability import read_capability

        d = MagicMock()
        d.capabilities = {"appium:appPackage": "", "appPackage": "com.real"}
        assert read_capability(d, "appium:appPackage", "appPackage", caller="t") == "com.real"

    def test_missing_key_returns_empty(self):
        from mobius.utils.capability import read_capability

        d = MagicMock()
        d.capabilities = {"platformName": "Android"}
        assert read_capability(d, "appium:appPackage", caller="t") == ""

    def test_non_mapping_capabilities_returns_empty(self):
        from mobius.utils.capability import read_capability

        d = MagicMock()
        d.capabilities = MagicMock()
        assert read_capability(d, "appium:appPackage", caller="t") == ""

    def test_non_string_value_is_ignored_not_stringified(self):
        from mobius.utils.capability import read_capability

        d = MagicMock()
        d.capabilities = {"appium:appPackage": {"nested": "dict"}}
        assert read_capability(d, "appium:appPackage", caller="t") == ""

    def test_unreadable_capabilities_returns_empty(self):
        from mobius.utils.capability import read_capability

        d = MagicMock()
        type(d).capabilities = property(lambda self: (_ for _ in ()).throw(Exception("boom")))
        assert read_capability(d, "appium:appPackage", caller="t") == ""


@pytest.mark.unit
class TestNetworkDeadDriver:
    """
    «Профиль не применился» и «драйвера больше нет» обязаны различаться:
    иначе тест в offline на мёртвой сессии выглядит как корректный негатив.
    """

    def test_go_offline_rethrows_dead_session(self):
        from selenium.common.exceptions import InvalidSessionIdException

        d = MagicMock()
        d.set_network_connection.side_effect = InvalidSessionIdException("invalid session id 'x'")
        sim = NetworkSimulator(d)
        with pytest.raises(InvalidSessionIdException):
            sim.go_offline()
        assert sim.current_profile is None

    def test_set_profile_rethrows_transport_failure(self):
        d = MagicMock()
        d.execute_script.side_effect = OSError("[Errno 111] Connection refused")
        sim = NetworkSimulator(d)
        with pytest.raises(OSError):
            sim.set_profile(NetworkProfile.THREE_G)
        assert sim.current_profile is None

    def test_leaving_offline_rethrows_instead_of_claiming_a_profile(self):
        from selenium.common.exceptions import InvalidSessionIdException

        d = MagicMock()
        sim = NetworkSimulator(d)
        assert sim.go_offline() is True
        d.set_network_connection.side_effect = InvalidSessionIdException("invalid session id 'x'")

        with pytest.raises(InvalidSessionIdException):
            sim.set_profile(NetworkProfile.LTE)

        # Сессия мертва — прогон обязан упасть, а не остаться со «stable offline».
        assert sim.current_profile is NetworkProfile.OFFLINE
