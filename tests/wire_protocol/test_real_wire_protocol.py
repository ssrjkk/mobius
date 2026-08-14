"""
Wire-protocol тесты — реальный HTTP через настоящий Appium-Python-Client
против локального fake WebDriver сервера. НЕ mock: framework код реально
сериализует JSON, реально открывает TCP-соединение на localhost, реально
получает ответ и парсит его.

Это самая сильная проверка достижимая без физического Android/iOS
устройства в этой среде. Единственное отличие от прода — на другом конце
провода fake-сервер, а не настоящий Appium+эмулятор.

Именно эти тесты поймали бы баг ADR-001 (desired_capabilities) на уровне
'сервер получил TypeError до отправки запроса' — раньше это пряталось
за pragma: no cover, потому что 'требует реальный сервер'. Теперь не требует.
"""

from __future__ import annotations

import pytest
from appium.webdriver.common.appiumby import AppiumBy

from tests.wire_protocol.fake_webdriver_server import FakeWebDriverServer


@pytest.mark.wire_protocol
class TestSessionCreation:
    """create_driver() — самое важное: раньше здесь был реальный баг (ADR-001)."""

    def test_session_created_successfully(self, wire_driver) -> None:
        assert wire_driver.session_id is not None

    def test_capabilities_sent_in_w3c_envelope(
        self, wire_server: FakeWebDriverServer, wire_driver
    ) -> None:
        req = wire_server.last_request("POST", "/session")
        assert req is not None
        assert "capabilities" in req.body
        assert "alwaysMatch" in req.body["capabilities"]

    def test_platform_name_reaches_server_correctly(
        self, wire_server: FakeWebDriverServer, wire_driver
    ) -> None:
        req = wire_server.last_request("POST", "/session")
        sent_caps = req.body["capabilities"]["alwaysMatch"]
        assert sent_caps["platformName"] == "Android"

    def test_device_name_reaches_server_correctly(
        self, wire_server: FakeWebDriverServer, wire_driver
    ) -> None:
        req = wire_server.last_request("POST", "/session")
        sent_caps = req.body["capabilities"]["alwaysMatch"]
        assert sent_caps["appium:deviceName"] == "Pixel 6"

    def test_automation_name_reaches_server_correctly(
        self, wire_server: FakeWebDriverServer, wire_driver
    ) -> None:
        req = wire_server.last_request("POST", "/session")
        sent_caps = req.body["capabilities"]["alwaysMatch"]
        assert sent_caps["appium:automationName"] == "UiAutomator2"

    def test_no_desired_capabilities_key_sent(
        self, wire_server: FakeWebDriverServer, wire_driver
    ) -> None:
        """
        Регрессия ADR-001: старый (сломанный) код слал бы TypeError ДО того
        как запрос вообще ушёл. Раз запрос дошёл — используется правильный
        W3C формат, не legacy 'desiredCapabilities'.
        """
        req = wire_server.last_request("POST", "/session")
        assert "desiredCapabilities" not in req.body

    def test_session_deleted_on_quit(self, wire_server: FakeWebDriverServer) -> None:
        from mobius.driver.appium_driver import create_driver
        from mobius.driver.capabilities import pixel_6_api33

        driver = create_driver(pixel_6_api33(), server_url=wire_server.url)
        session_id = driver.session_id
        driver.quit()

        delete_req = wire_server.last_request("DELETE", f"/session/{session_id}")
        assert delete_req is not None


@pytest.mark.wire_protocol
class TestElementInteraction:
    """find_element / click / send_keys — базовые команды Screen Object слоя."""

    def test_find_element_sends_correct_strategy(
        self, wire_server: FakeWebDriverServer, wire_driver
    ) -> None:
        wire_driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Login button")
        elem_req = wire_server.last_request("POST", "/element")
        assert elem_req is not None
        assert elem_req.body["using"] == "accessibility id"
        assert elem_req.body["value"] == "Login button"

    def test_click_hits_correct_element_endpoint(
        self, wire_server: FakeWebDriverServer, wire_driver
    ) -> None:
        elem = wire_driver.find_element(AppiumBy.ID, "btn")
        elem.click()
        click_req = wire_server.last_request("POST", "/click")
        assert click_req is not None
        assert "/element/" in click_req.path

    def test_send_keys_sends_text_value(
        self, wire_server: FakeWebDriverServer, wire_driver
    ) -> None:
        elem = wire_driver.find_element(AppiumBy.ID, "input")
        elem.send_keys("test@example.com")
        value_req = wire_server.last_request("POST", "/value")
        assert value_req is not None


@pytest.mark.wire_protocol
class TestGesturesRealWireFormat:
    """
    Самая сложная часть framework — W3C Actions для жестов. Проверяем что
    математика координат (mobius/utils/gestures.py) реально доходит
    до сервера в правильном формате.
    """

    def test_swipe_up_sends_w3c_actions_payload(
        self, wire_server: FakeWebDriverServer, wire_driver
    ) -> None:
        from mobius.utils.gestures import Gestures, SwipeDirection

        g = Gestures(wire_driver)
        g.swipe(SwipeDirection.UP)

        req = wire_server.last_request("POST", "/actions")
        assert req is not None
        pointer_actions = req.body["actions"][0]["actions"]
        assert pointer_actions[0]["type"] == "pointerMove"
        assert pointer_actions[1]["type"] == "pointerDown"
        assert pointer_actions[3]["type"] == "pointerUp"

    def test_swipe_up_coordinates_match_calculate_swipe_coords_formula(
        self, wire_server: FakeWebDriverServer, wire_driver
    ) -> None:
        """
        Прямая проверка что реально отправленные координаты совпадают
        с чистой функцией calculate_swipe_coords — не просто 'запрос ушёл',
        а 'запрос содержит МАТЕМАТИЧЕСКИ ПРАВИЛЬНЫЕ координаты'.
        """
        from mobius.utils.gestures import Gestures, SwipeDirection

        expected_sx, expected_sy, expected_ex, expected_ey = Gestures.calculate_swipe_coords(
            {"width": 1080, "height": 2400}, SwipeDirection.UP
        )

        g = Gestures(wire_driver)
        g.swipe(SwipeDirection.UP)

        req = wire_server.last_request("POST", "/actions")
        pointer_actions = req.body["actions"][0]["actions"]
        move_start = pointer_actions[0]
        move_end = pointer_actions[2]

        assert move_start["x"] == expected_sx
        assert move_start["y"] == expected_sy
        assert move_end["x"] == expected_ex
        assert move_end["y"] == expected_ey

    def test_swipe_direction_affects_wire_coordinates(
        self, wire_server: FakeWebDriverServer, wire_driver
    ) -> None:
        """UP и DOWN должны реально отличаться в отправленных координатах."""
        from mobius.utils.gestures import Gestures, SwipeDirection

        g = Gestures(wire_driver)
        g.swipe(SwipeDirection.UP)
        up_req = wire_server.last_request("POST", "/actions")
        up_y_start = up_req.body["actions"][0]["actions"][0]["y"]

        g.swipe(SwipeDirection.DOWN)
        down_req = wire_server.last_request("POST", "/actions")
        down_y_start = down_req.body["actions"][0]["actions"][0]["y"]

        assert up_y_start != down_y_start


@pytest.mark.wire_protocol
class TestDeviceActionsRealWireFormat:
    def test_rotate_to_landscape_sends_orientation_command(
        self, wire_server: FakeWebDriverServer, wire_driver
    ) -> None:
        from mobius.utils.device import DeviceActions

        DeviceActions(wire_driver).rotate_to_landscape()
        req = wire_server.last_request("POST", "/orientation")
        assert req is not None
        assert req.body["orientation"] == "LANDSCAPE"

    def test_press_back_sends_correct_keycode(
        self, wire_server: FakeWebDriverServer, wire_driver
    ) -> None:
        from mobius.utils.device import DeviceActions, HardwareKey

        DeviceActions(wire_driver).press_back()
        req = wire_server.last_request("POST", "/execute/sync")
        assert req is not None
        assert req.body["script"] == "mobile: pressKey"
        assert req.body["args"][0]["keycode"] == HardwareKey.BACK.value


@pytest.mark.wire_protocol
class TestPermissionsRealWireFormat:
    def test_grant_sends_correct_mobile_command(
        self, wire_server: FakeWebDriverServer, wire_driver
    ) -> None:
        from mobius.utils.permissions import Permission, PermissionsManager

        PermissionsManager(wire_driver, app_package="com.example.app").grant(Permission.CAMERA)
        req = wire_server.last_request("POST", "/execute/sync")
        assert req is not None
        assert req.body["script"] == "mobile: changePermissions"
        assert req.body["args"][0]["permissions"] == ["camera"]
        assert req.body["args"][0]["action"] == "grant"
        assert req.body["args"][0]["appPackage"] == "com.example.app"


@pytest.mark.wire_protocol
class TestDevicePoolRealWireFormat:
    """DevicePool → capabilities → реальный HTTP: порт реально доходит до сервера."""

    def test_assigned_system_port_reaches_real_session_request(
        self, wire_server: FakeWebDriverServer
    ) -> None:
        from mobius.driver.appium_driver import create_driver
        from mobius.driver.capabilities import AutomationName, DeviceCapabilities, Platform
        from mobius.driver.device_pool import DevicePool

        pool = DevicePool()
        pool.register("emulator-5554", Platform.ANDROID, "13.0", "Pixel 6")
        pool.register("emulator-5556", Platform.ANDROID, "14.0", "Pixel 7")

        device = pool.get_for_worker("gw1")
        caps = DeviceCapabilities(
            platform=Platform.ANDROID,
            device_name=device.device_name,
            platform_version=device.platform_version,
            automation_name=AutomationName.UIAUTOMATOR2,
            extra=pool.to_capabilities_extra(device),
        )

        driver = create_driver(caps, server_url=wire_server.url)
        try:
            req = wire_server.last_request("POST", "/session")
            sent_caps = req.body["capabilities"]["alwaysMatch"]
            assert sent_caps["appium:systemPort"] == device.system_port
            assert sent_caps["appium:udid"] == device.udid
        finally:
            driver.quit()

    def test_two_workers_produce_non_colliding_real_requests(
        self, wire_server: FakeWebDriverServer
    ) -> None:
        from mobius.driver.appium_driver import create_driver
        from mobius.driver.capabilities import AutomationName, DeviceCapabilities, Platform
        from mobius.driver.device_pool import DevicePool

        pool = DevicePool()
        pool.register("emulator-5554", Platform.ANDROID, "13.0", "Pixel 6")
        pool.register("emulator-5556", Platform.ANDROID, "14.0", "Pixel 7")

        drivers, sent_ports = [], []
        for worker_id in ("gw0", "gw1"):
            device = pool.get_for_worker(worker_id)
            caps = DeviceCapabilities(
                platform=Platform.ANDROID,
                device_name=device.device_name,
                platform_version=device.platform_version,
                automation_name=AutomationName.UIAUTOMATOR2,
                extra=pool.to_capabilities_extra(device),
            )
            d = create_driver(caps, server_url=wire_server.url)
            drivers.append(d)
            req = wire_server.last_request("POST", "/session")
            sent_ports.append(req.body["capabilities"]["alwaysMatch"]["appium:systemPort"])

        for d in drivers:
            d.quit()

        assert sent_ports[0] != sent_ports[1]


@pytest.mark.wire_protocol
class TestUniversalFinderRealWireFormat:
    def test_find_any_button_sends_correct_xpath(
        self, wire_server: FakeWebDriverServer, wire_driver
    ) -> None:
        from mobius.utils.universal_finder import UniversalFinder

        UniversalFinder(wire_driver).find_any_button()
        req = wire_server.last_request("POST", "/elements")
        assert req is not None
        assert req.body["using"] == "xpath"
        assert "android.widget.Button" in req.body["value"]

    def test_find_by_text_sends_contains_xpath(
        self, wire_server: FakeWebDriverServer, wire_driver
    ) -> None:
        from mobius.utils.universal_finder import UniversalFinder

        try:
            UniversalFinder(wire_driver).find_by_text("Welcome")
        except Exception:
            pass  # fake сервер не умеет find_element вернуть осмысленно для проверки текста

        req = wire_server.last_request("POST", "/element")
        assert req is not None
        assert "Welcome" in req.body["value"]
        assert "contains(" in req.body["value"]
