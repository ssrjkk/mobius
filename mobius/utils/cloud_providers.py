"""Cloud device providers — Sauce Labs и BrowserStack для DevicePool."""

from __future__ import annotations

import os

from mobius.driver.capabilities import AutomationName, DeviceCapabilities, Platform
from mobius.driver.device_pool import Device, DevicePool
from mobius.logging_config import get_logger

logger = get_logger(__name__)


class SauceLabsProvider:
    @staticmethod
    def build_pool(platforms: list[dict[str, str]]) -> DevicePool:
        pool = DevicePool()
        for p in platforms:
            platform = Platform.ANDROID if p["platform"].lower() == "android" else Platform.IOS
            pool.register(
                udid=p.get("udid", p["device"].replace(" ", "_").lower()),
                platform=platform,
                platform_version=p["version"],
                device_name=p["device"],
            )
        pool.assert_no_port_collisions()
        return pool

    @staticmethod
    def capabilities_for(
        device: Device,
        app_path: str | None = None,
        tunnel_id: str | None = None,
        build_name: str | None = None,
        test_name: str | None = None,
    ) -> DeviceCapabilities:
        username = os.environ.get("SAUCE_USERNAME", "")
        access_key = os.environ.get("SAUCE_ACCESS_KEY", "")
        if not username or not access_key:
            logger.warning(
                "SauceLabsProvider: SAUCE_USERNAME / SAUCE_ACCESS_KEY not set "
                "— capabilities generated but create_driver() will fail"
            )
        automation = (
            AutomationName.UIAUTOMATOR2
            if device.platform == Platform.ANDROID
            else AutomationName.XCUITEST
        )
        sauce_options: dict[str, str] = {"appiumVersion": "latest"}
        if build_name:
            sauce_options["build"] = build_name
        if test_name:
            sauce_options["name"] = test_name
        if tunnel_id:
            sauce_options["tunnelIdentifier"] = tunnel_id
        extra: dict[str, object] = {
            "appium:deviceName": device.device_name,
            "sauce:options": sauce_options,
        }
        if device.platform == Platform.ANDROID:
            extra["appium:platformVersion"] = device.platform_version
        return DeviceCapabilities(
            platform=device.platform,
            device_name=device.device_name,
            platform_version=device.platform_version,
            automation_name=automation,
            app=app_path or os.environ.get("APP_PATH"),
            extra=extra,
        )


class BrowserStackProvider:
    BROWSERSTACK_HUB = "https://hub-cloud.browserstack.com/wd/hub"

    @staticmethod
    def build_pool(platforms: list[dict[str, str]]) -> DevicePool:
        pool = DevicePool()
        for p in platforms:
            platform = Platform.ANDROID if p["platform"].lower() == "android" else Platform.IOS
            pool.register(
                udid=p.get("device", "").replace(" ", "_").lower(),
                platform=platform,
                platform_version=p["os_version"],
                device_name=p["device"],
            )
        pool.assert_no_port_collisions()
        return pool

    @staticmethod
    def capabilities_for(
        device: Device,
        app_id: str | None = None,
        project: str | None = None,
        build: str | None = None,
        test_name: str | None = None,
    ) -> DeviceCapabilities:
        username = os.environ.get("BROWSERSTACK_USER", "")
        access_key = os.environ.get("BROWSERSTACK_KEY", "")
        if not username or not access_key:
            logger.warning("BrowserStackProvider: BROWSERSTACK_USER / BROWSERSTACK_KEY not set")
        automation = (
            AutomationName.UIAUTOMATOR2
            if device.platform == Platform.ANDROID
            else AutomationName.XCUITEST
        )
        bstack_options: dict[str, object] = {
            "userName": username,
            "accessKey": access_key,
            "enableBiometric": True,
        }
        if project:
            bstack_options["projectName"] = project
        if build:
            bstack_options["buildName"] = build
        if test_name:
            bstack_options["sessionName"] = test_name
        return DeviceCapabilities(
            platform=device.platform,
            device_name=device.device_name,
            platform_version=device.platform_version,
            automation_name=automation,
            app=app_id or os.environ.get("APP_PATH"),
            extra={"bstack:options": bstack_options},
        )
