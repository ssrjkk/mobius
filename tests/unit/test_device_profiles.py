"""
Unit tests — mobius.driver.device_profiles.DeviceProfileLoader.

Найден как orphaned-код (аналогично retry_config.py, ADR-008) —
существовал, работал, но не был протестирован/интегрирован. Ссылался
на несуществующий docs/device_profiles_example.yaml — исправлено на
реальный devices/ci_matrix_example.yaml.
"""

from __future__ import annotations

import json

import pytest

from mobius.driver.capabilities import AutomationName, Platform
from mobius.driver.device_profiles import DeviceProfileLoader


@pytest.fixture
def yaml_profiles_file(tmp_path):
    content = """
profiles:
  pixel_6_api33:
    platform: Android
    platform_version: "13.0"
    device_name: Pixel 6
    automation_name: UiAutomator2
    udid: emulator-5554
  iphone_15:
    platform: iOS
    platform_version: "17.0"
    device_name: iPhone 15
    bundle_id: com.example.app.ios
"""
    f = tmp_path / "profiles.yaml"
    f.write_text(content)
    return f


@pytest.fixture
def json_profiles_file(tmp_path):
    data = {
        "profiles": {
            "pixel_7": {
                "platform": "Android",
                "device_name": "Pixel 7",
                "platform_version": "14.0",
            }
        }
    }
    f = tmp_path / "profiles.json"
    f.write_text(json.dumps(data))
    return f


@pytest.mark.unit
class TestDeviceProfileLoaderYaml:
    def test_loads_available_profiles(self, yaml_profiles_file):
        loader = DeviceProfileLoader(yaml_profiles_file)
        assert set(loader.available()) == {"pixel_6_api33", "iphone_15"}

    def test_get_android_profile(self, yaml_profiles_file):
        loader = DeviceProfileLoader(yaml_profiles_file)
        caps = loader.get("pixel_6_api33")
        assert caps.platform == Platform.ANDROID
        assert caps.device_name == "Pixel 6"
        assert caps.udid == "emulator-5554"
        assert caps.automation_name == AutomationName.UIAUTOMATOR2

    def test_get_ios_profile(self, yaml_profiles_file):
        loader = DeviceProfileLoader(yaml_profiles_file)
        caps = loader.get("iphone_15")
        assert caps.platform == Platform.IOS
        assert caps.bundle_id == "com.example.app.ios"

    def test_ios_defaults_to_xcuitest_when_automation_not_specified(self, yaml_profiles_file):
        loader = DeviceProfileLoader(yaml_profiles_file)
        caps = loader.get("iphone_15")
        assert caps.automation_name == AutomationName.XCUITEST

    def test_get_all_returns_all_profiles(self, yaml_profiles_file):
        loader = DeviceProfileLoader(yaml_profiles_file)
        all_profiles = loader.get_all()
        assert len(all_profiles) == 2
        assert "pixel_6_api33" in all_profiles
        assert "iphone_15" in all_profiles

    def test_to_dict_produces_valid_capabilities(self, yaml_profiles_file):
        loader = DeviceProfileLoader(yaml_profiles_file)
        caps = loader.get("pixel_6_api33")
        d = caps.to_dict()
        assert d["platformName"] == "Android"
        assert d["appium:udid"] == "emulator-5554"


@pytest.mark.unit
class TestDeviceProfileLoaderJson:
    def test_loads_json_profiles(self, json_profiles_file):
        loader = DeviceProfileLoader(json_profiles_file)
        assert loader.available() == ["pixel_7"]

    def test_json_profile_capabilities_correct(self, json_profiles_file):
        loader = DeviceProfileLoader(json_profiles_file)
        caps = loader.get("pixel_7")
        assert caps.device_name == "Pixel 7"
        assert caps.platform_version == "14.0"


@pytest.mark.unit
class TestDeviceProfileLoaderErrors:
    def test_missing_file_raises_with_helpful_message(self, tmp_path):
        missing = tmp_path / "does_not_exist.yaml"
        with pytest.raises(FileNotFoundError, match="devices/ci_matrix_example.yaml"):
            DeviceProfileLoader(missing)

    def test_missing_profile_raises_keyerror_with_available_list(self, yaml_profiles_file):
        loader = DeviceProfileLoader(yaml_profiles_file)
        with pytest.raises(KeyError, match="not found"):
            loader.get("nonexistent_profile")

    def test_invalid_platform_raises_valueerror(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text("profiles:\n  bad_device:\n    platform: WindowsPhone\n    device_name: X\n")
        loader = DeviceProfileLoader(f)
        with pytest.raises(ValueError):
            loader.get("bad_device")

    def test_missing_device_name_raises_keyerror(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text("profiles:\n  incomplete:\n    platform: Android\n")
        loader = DeviceProfileLoader(f)
        with pytest.raises(KeyError):
            loader.get("incomplete")

    def test_yaml_import_error_gives_helpful_message(self, tmp_path, monkeypatch):
        """Тот же паттерн что test_app_config_yaml_import_error_raises_helpful_message."""
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError("No module named 'yaml'")
            return real_import(name, *args, **kwargs)

        f = tmp_path / "profiles.yaml"
        f.write_text("profiles:\n  x:\n    platform: Android\n    device_name: X\n")

        monkeypatch.setattr(builtins, "__import__", fake_import)
        with pytest.raises(ImportError, match="pip install pyyaml"):
            DeviceProfileLoader(f)


@pytest.mark.unit
class TestDeviceProfileLoaderExampleFile:
    """Проверяет что реальный devices/ci_matrix_example.yaml валиден и загружается."""

    def test_example_file_exists_and_loads(self):
        from pathlib import Path

        example_path = Path(__file__).parent.parent.parent / "devices" / "ci_matrix_example.yaml"
        assert example_path.exists(), (
            "devices/ci_matrix_example.yaml referenced in error message must exist"
        )
        loader = DeviceProfileLoader(example_path)
        assert len(loader.available()) >= 2

    def test_example_file_has_both_platforms(self):
        from pathlib import Path

        example_path = Path(__file__).parent.parent.parent / "devices" / "ci_matrix_example.yaml"
        loader = DeviceProfileLoader(example_path)
        platforms = {loader.get(name).platform for name in loader.available()}
        assert Platform.ANDROID in platforms
        assert Platform.IOS in platforms
