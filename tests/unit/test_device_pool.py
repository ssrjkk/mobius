"""
Unit tests — DevicePool: распределение устройств и портов для параллельного
выполнения. Без реального Appium/устройства — чистая логика распределения.
"""

from __future__ import annotations

import pytest

from mobius.driver.capabilities import Platform
from mobius.driver.device_pool import Device, DevicePool


def _make_pool(n_android: int = 2, n_ios: int = 1) -> DevicePool:
    pool = DevicePool()
    for i in range(n_android):
        pool.register(f"emulator-{5554 + i * 2}", Platform.ANDROID, "13.0", f"Pixel-{i}")
    for i in range(n_ios):
        pool.register(f"ios-udid-{i}", Platform.IOS, "17.0", f"iPhone-{i}")
    return pool


@pytest.mark.unit
class TestDevicePoolRegistration:
    def test_register_returns_device(self):
        pool = DevicePool()
        device = pool.register("emulator-5554", Platform.ANDROID, "13.0", "Pixel 6")
        assert isinstance(device, Device)
        assert device.udid == "emulator-5554"

    def test_len_reflects_registered_count(self):
        pool = _make_pool(n_android=3, n_ios=2)
        assert len(pool) == 5

    def test_devices_property_returns_copy(self):
        pool = _make_pool()
        devices_a = pool.devices
        devices_a.clear()
        assert len(pool) == 3  # исходный пул не пострадал

    def test_first_device_gets_base_ports(self):
        pool = DevicePool()
        device = pool.register("d1", Platform.ANDROID, "13.0", "D1")
        assert device.system_port == DevicePool.SYSTEM_PORT_BASE
        assert device.wda_local_port == DevicePool.WDA_LOCAL_PORT_BASE

    def test_second_device_gets_incremented_ports(self):
        pool = DevicePool()
        pool.register("d1", Platform.ANDROID, "13.0", "D1")
        d2 = pool.register("d2", Platform.ANDROID, "13.0", "D2")
        assert d2.system_port == DevicePool.SYSTEM_PORT_BASE + 1


@pytest.mark.unit
class TestDevicePoolNoCollisions:
    def test_no_collisions_with_many_devices(self):
        pool = _make_pool(n_android=10, n_ios=5)
        pool.assert_no_port_collisions()  # не падает

    def test_all_system_ports_unique(self):
        pool = _make_pool(n_android=5, n_ios=0)
        ports = [d.system_port for d in pool.devices]
        assert len(ports) == len(set(ports))

    def test_all_wda_ports_unique(self):
        pool = _make_pool(n_android=0, n_ios=5)
        ports = [d.wda_local_port for d in pool.devices]
        assert len(ports) == len(set(ports))

    def test_mixed_platform_ports_unique(self):
        """Android и iOS в одном пуле — порты всё равно не пересекаются между собой."""
        pool = _make_pool(n_android=3, n_ios=3)
        system_ports = [d.system_port for d in pool.devices]
        wda_ports = [d.wda_local_port for d in pool.devices]
        assert len(set(system_ports)) == 6
        assert len(set(wda_ports)) == 6


@pytest.mark.unit
class TestDevicePoolWorkerAssignment:
    def test_get_for_worker_gw0(self):
        pool = _make_pool(n_android=3, n_ios=0)
        device = pool.get_for_worker("gw0")
        assert device.udid == "emulator-5554"

    def test_get_for_worker_gw1(self):
        pool = _make_pool(n_android=3, n_ios=0)
        device = pool.get_for_worker("gw1")
        assert device.udid == "emulator-5556"

    def test_get_for_worker_wraps_around(self):
        """Больше worker'ов чем устройств — round-robin, не падение."""
        pool = _make_pool(n_android=2, n_ios=0)
        d_gw0 = pool.get_for_worker("gw0")
        d_gw2 = pool.get_for_worker("gw2")  # 2 % 2 == 0
        assert d_gw0.udid == d_gw2.udid

    def test_get_for_worker_none_returns_first_device(self):
        pool = _make_pool()
        device = pool.get_for_worker(None)
        assert device.udid == pool.devices[0].udid

    def test_get_for_worker_master_returns_first_device(self):
        """pytest-xdist без -n использует worker_id='master'."""
        pool = _make_pool()
        device = pool.get_for_worker("master")
        assert device.udid == pool.devices[0].udid

    def test_get_for_worker_empty_pool_raises(self):
        pool = DevicePool()
        with pytest.raises(ValueError, match="no devices registered"):
            pool.get_for_worker("gw0")

    def test_different_workers_get_different_devices(self):
        """Ключевое свойство: параллельные worker'ы не должны драться за одно устройство."""
        pool = _make_pool(n_android=4, n_ios=0)
        assigned = {pool.get_for_worker(f"gw{i}").udid for i in range(4)}
        assert len(assigned) == 4  # все разные


@pytest.mark.unit
class TestDevicePoolCapabilitiesExtra:
    def test_android_extra_has_system_port(self):
        pool = _make_pool(n_android=1, n_ios=0)
        device = pool.devices[0]
        extra = pool.to_capabilities_extra(device)
        assert "appium:systemPort" in extra
        assert "appium:wdaLocalPort" not in extra

    def test_ios_extra_has_wda_port_not_system_port(self):
        pool = _make_pool(n_android=0, n_ios=1)
        device = pool.devices[0]
        extra = pool.to_capabilities_extra(device)
        assert "appium:wdaLocalPort" in extra
        assert "appium:systemPort" not in extra

    def test_android_extra_has_chromedriver_port(self):
        pool = _make_pool(n_android=1, n_ios=0)
        extra = pool.to_capabilities_extra(pool.devices[0])
        assert "appium:chromedriverPort" in extra

    def test_extra_always_has_udid(self):
        pool = _make_pool(n_android=1, n_ios=0)
        extra = pool.to_capabilities_extra(pool.devices[0])
        assert extra["appium:udid"] == pool.devices[0].udid

    def test_extra_has_mjpeg_port_both_platforms(self):
        pool = _make_pool(n_android=1, n_ios=1)
        for device in pool.devices:
            extra = pool.to_capabilities_extra(device)
            assert "appium:mjpegServerPort" in extra

    def test_two_devices_produce_non_colliding_extras(self):
        pool = _make_pool(n_android=2, n_ios=0)
        extra1 = pool.to_capabilities_extra(pool.devices[0])
        extra2 = pool.to_capabilities_extra(pool.devices[1])
        assert extra1["appium:systemPort"] != extra2["appium:systemPort"]
        assert extra1["appium:udid"] != extra2["appium:udid"]


@pytest.mark.unit
class TestDevicePoolNullPorts:
    """Покрываем ветки когда device.system_port / wda_local_port == None."""

    def test_device_with_none_system_port_excluded_from_extra(self):
        from mobius.driver.device_pool import Device

        pool = DevicePool()
        device = Device(
            udid="test",
            platform=Platform.ANDROID,
            platform_version="13.0",
            device_name="Test",
            system_port=None,
            chromedriver_port=None,
            mjpeg_server_port=None,
        )
        pool._devices.append(device)
        extra = pool.to_capabilities_extra(device)
        assert "appium:systemPort" not in extra
        assert "appium:mjpegServerPort" not in extra
        assert extra["appium:udid"] == "test"

    def test_device_with_none_wda_port_excluded_from_extra(self):
        from mobius.driver.device_pool import Device

        pool = DevicePool()
        device = Device(
            udid="ios-test",
            platform=Platform.IOS,
            platform_version="17.0",
            device_name="iPhone",
            wda_local_port=None,
            mjpeg_server_port=None,
        )
        pool._devices.append(device)
        extra = pool.to_capabilities_extra(device)
        assert "appium:wdaLocalPort" not in extra

    def test_assert_no_port_collisions_raises_on_duplicate(self):
        from mobius.driver.device_pool import Device

        pool = DevicePool()
        for i in range(2):
            d = Device(
                udid=f"d{i}",
                platform=Platform.ANDROID,
                platform_version="13.0",
                device_name=f"D{i}",
                system_port=8200,  # намеренная коллизия
            )
            pool._devices.append(d)
        with pytest.raises(AssertionError, match="port collision"):
            pool.assert_no_port_collisions()
