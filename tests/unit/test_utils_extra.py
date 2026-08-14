"""Unit tests — deeplink, network, performance, accessibility, screenshot."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mobius.utils.accessibility import A11yReport, AccessibilityChecker
from mobius.utils.deeplink import DeepLink
from mobius.utils.network import PROFILES, NetworkCondition, NetworkProfile, NetworkSimulator
from mobius.utils.performance import PerformanceCollector
from mobius.utils.screenshot import ScreenshotUtils


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
        self.n.go_offline()
        assert self.n.current_profile == NetworkProfile.OFFLINE

    def test_go_offline_exception_swallowed(self):
        self.d.set_network_connection.side_effect = Exception("no api")
        self.n.go_offline()
        assert self.n.current_profile == NetworkProfile.OFFLINE

    def test_go_online(self):
        self.n.go_online()
        assert self.n.current_profile == NetworkProfile.WIFI

    def test_go_online_exception_swallowed(self):
        self.d.set_network_connection.side_effect = Exception("no api")
        self.n.go_online()
        assert self.n.current_profile == NetworkProfile.WIFI

    def test_set_profile_lte(self):
        with patch.object(self.n, "_apply"):
            self.n.set_profile(NetworkProfile.LTE)
        assert self.n.current_profile == NetworkProfile.LTE

    def test_set_profile_wifi(self):
        with patch.object(self.n, "_apply"):
            self.n.set_profile(NetworkProfile.WIFI)
        assert self.n.current_profile == NetworkProfile.WIFI

    def test_set_profile_2g(self):
        with patch.object(self.n, "_apply"):
            self.n.set_profile(NetworkProfile.TWO_G)
        assert self.n.current_profile == NetworkProfile.TWO_G

    def test_set_profile_offline_calls_go_offline(self):
        with patch.object(self.n, "go_offline") as m:
            self.n.set_profile(NetworkProfile.OFFLINE)
        m.assert_called_once()

    def test_apply_exception_swallowed(self):
        self.d.execute_script.side_effect = Exception("not supported")
        self.n._apply(PROFILES[NetworkProfile.LTE])

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
        checker = AccessibilityChecker(MagicMock())
        report = A11yReport()
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
        checker._check_element(elem, report)
        assert any("small" in v.issue for v in report.violations)

    def test_check_element_missing_content_desc_error(self):
        checker = AccessibilityChecker(MagicMock())
        report = A11yReport()
        elem = MagicMock()
        elem.tag_name = "android.widget.ImageView"
        elem.get_attribute.side_effect = lambda k: {
            "clickable": "true",
            "content-desc": "",
            "resource-id": "img",
        }.get(k, "")
        elem.text = ""
        elem.is_displayed.return_value = True
        elem.size = {"width": 100, "height": 100}
        checker._check_element(elem, report)
        assert any(v.severity == "error" for v in report.violations)

    def test_check_element_image_missing_alt(self):
        checker = AccessibilityChecker(MagicMock())
        report = A11yReport()
        elem = MagicMock()
        elem.tag_name = "android.widget.ImageView"
        elem.get_attribute.side_effect = lambda k: {
            "clickable": "false",
            "content-desc": "",
            "resource-id": "img_hero",
        }.get(k, "")
        elem.text = ""
        elem.is_displayed.return_value = True
        elem.size = {"width": 200, "height": 200}
        checker._check_element(elem, report)
        assert any("Image" in v.issue for v in report.violations)

    def test_check_element_non_clickable_passes(self):
        checker = AccessibilityChecker(MagicMock())
        report = A11yReport()
        elem = MagicMock()
        elem.tag_name = "android.widget.TextView"
        elem.get_attribute.side_effect = lambda k: {
            "clickable": "false",
            "content-desc": "Hello",
            "resource-id": "txt",
        }.get(k, "")
        elem.text = "Hello"
        elem.is_displayed.return_value = True
        elem.size = {"width": 200, "height": 40}
        checker._check_element(elem, report)
        assert report.passed >= 1

    def test_check_element_large_touch_target_ok(self):
        checker = AccessibilityChecker(MagicMock())
        report = A11yReport()
        elem = MagicMock()
        elem.tag_name = "android.widget.Button"
        elem.get_attribute.side_effect = lambda k: {
            "clickable": "true",
            "content-desc": "Submit",
            "resource-id": "btn_submit",
        }.get(k, "")
        elem.text = ""
        elem.is_displayed.return_value = False
        elem.size = {"width": 200, "height": 100}
        checker._check_element(elem, report)
        size_violations = [v for v in report.violations if "small" in v.issue]
        assert len(size_violations) == 0


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
