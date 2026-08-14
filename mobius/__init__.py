"""
Mobius — Universal Mobile QA Automation Framework.
Android / iOS · Appium 2.x · pytest · Allure

Author:  Ситников Сергей (ssrjkk)
Email:   ray013lefe@gmail.com
GitHub:  https://github.com/ssrjkk/mobius
License: MIT
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

try:
    __version__ = _version("mobius")
except PackageNotFoundError:  # pragma: no cover
    # Запущено из исходников без pip install -e . — редкий edge case,
    # не должен ронять импорт всего пакета.
    __version__ = "0.0.0+unknown"

__author__ = "Ситников Сергей"
__email__ = "ray013lefe@gmail.com"
__github__ = "https://github.com/ssrjkk/mobius"

# ── Driver / Capabilities ────────────────────────────────────────────────────
from mobius.driver.appium_driver import (
    ServerMode,
    create_driver,
    is_appium_available,
)
from mobius.driver.capabilities import (
    AutomationName,
    DeviceCapabilities,
    Platform,
    ResetStrategy,
    from_env,
    iphone_15_ios17,
    pixel_6_api33,
    pixel_7_api34,
)
from mobius.driver.device_pool import Device, DevicePool
from mobius.driver.device_profiles import DeviceProfileLoader

# ── Elements ─────────────────────────────────────────────────────────────────
from mobius.elements.mobile_element import MobileElement

# ── Screen Objects ───────────────────────────────────────────────────────────
from mobius.screens.base_screen import BaseScreen
from mobius.utils.accessibility import A11yReport, AccessibilityChecker
from mobius.utils.alerts import SystemAlertHandler
from mobius.utils.app_config import AppConfig, ConfigDrivenScreen, LocatorSpec
from mobius.utils.app_lifecycle import AppInstaller
from mobius.utils.biometrics import BiometricSimulator, BiometricType
from mobius.utils.clipboard import ClipboardManager
from mobius.utils.cloud_providers import BrowserStackProvider, SauceLabsProvider
from mobius.utils.deeplink import DeepLink
from mobius.utils.device import DeviceActions, HardwareKey, Orientation
from mobius.utils.device_logs import CrashReport, DeviceLogCollector
from mobius.utils.file_transfer import FileTransfer

# ── Universal Utils ───────────────────────────────────────────────────────────
from mobius.utils.gestures import Gestures, SwipeDirection
from mobius.utils.interruptions import InterruptionSimulator
from mobius.utils.locale import LocaleManager
from mobius.utils.network import NetworkProfile, NetworkSimulator
from mobius.utils.notifications import NotificationHelper
from mobius.utils.performance import PerformanceCollector
from mobius.utils.permissions import Permission, PermissionAction, PermissionsManager
from mobius.utils.platform_info import get_platform_name, is_android, is_ios
from mobius.utils.retry_config import (
    RetryConfig,
    configure_rerun_filter,
    is_infrastructure_error,
)
from mobius.utils.screen_recording import ScreenRecorder
from mobius.utils.screenshot import ScreenshotUtils
from mobius.utils.test_isolation import AppResetHelper
from mobius.utils.universal_finder import UniversalFinder
from mobius.utils.visual_regression import VisualDiffResult, VisualRegression
from mobius.utils.wait_utils import RetryDecorator, WaitUtils
from mobius.utils.webview import WebViewContext

__all__ = [
    # Capabilities & Driver
    "Platform",
    "AutomationName",
    "ResetStrategy",
    "DeviceCapabilities",
    "pixel_6_api33",
    "pixel_7_api34",
    "iphone_15_ios17",
    "from_env",
    "ServerMode",
    "create_driver",
    "is_appium_available",
    # DevicePool
    "Device",
    "DevicePool",
    "DeviceProfileLoader",
    # Screens & Elements
    "BaseScreen",
    "MobileElement",
    # Gestures & Waits
    "Gestures",
    "SwipeDirection",
    "WaitUtils",
    "RetryDecorator",
    # Device
    "DeviceActions",
    "HardwareKey",
    "Orientation",
    # Alerts & Permissions
    "SystemAlertHandler",
    "Permission",
    "PermissionAction",
    "PermissionsManager",
    # Clipboard, Locale, Notifications
    "ClipboardManager",
    "LocaleManager",
    "NotificationHelper",
    # Finder & Platform
    "UniversalFinder",
    "is_android",
    "is_ios",
    "get_platform_name",
    # Network & Performance
    "NetworkSimulator",
    "NetworkProfile",
    "PerformanceCollector",
    # Accessibility
    "AccessibilityChecker",
    "A11yReport",
    # WebView & Visual
    "WebViewContext",
    "VisualRegression",
    "VisualDiffResult",
    # Files & Logs
    "FileTransfer",
    "DeviceLogCollector",
    "CrashReport",
    # Hardware simulation
    "BiometricSimulator",
    "BiometricType",
    "InterruptionSimulator",
    # App management
    "AppInstaller",
    "ScreenRecorder",
    "ScreenshotUtils",
    # Config-driven
    "AppConfig",
    "ConfigDrivenScreen",
    "LocatorSpec",
    # Deep link
    "DeepLink",
    # Test isolation
    "AppResetHelper",
    # Cloud device providers
    "SauceLabsProvider",
    "BrowserStackProvider",
    # Smart retry
    "RetryConfig",
    "is_infrastructure_error",
    "configure_rerun_filter",
]
