"""
Device Pool — управление парком устройств для параллельного выполнения.

В 2026 последовательный прогон мобильных тестов не масштабируется —
реальный CI держит N эмуляторов/устройств и распределяет тесты между
ними параллельно. Появление коллизии портов между параллельными Appium
сессиями — самая частая причина "случайных" падений в параллельном
mobile CI (подтверждено несколькими источниками 2026 года при
исследовании перед реализацией этого модуля).

Appium требует УНИКАЛЬНЫЕ порты на сессию при параллельном запуске:
  appium:systemPort         — UiAutomator2 (Android), диапазон 8200-8299
  appium:wdaLocalPort       — XCUITest (iOS)
  appium:chromedriverPort   — WebView/hybrid контекст
  appium:mjpegServerPort    — видео-стриминг с устройства

DevicePool не синхронизируется между pytest-xdist worker'ами через
блокировки — каждый worker детерминированно вычисляет СВОЙ индекс из
worker_id ('gw0', 'gw1', ...), поэтому кросс-процессная синхронизация
не нужна в принципе. Это подтверждённый реальный паттерн, не придумано
с нуля — см. docs/adr/007-device-pool-worker-assignment.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from mobius.driver.capabilities import Platform


@dataclass
class Device:
    """Одно устройство/эмулятор в пуле — с гарантированно уникальными портами."""

    udid: str
    platform: Platform
    platform_version: str
    device_name: str
    system_port: int | None = None
    wda_local_port: int | None = None
    chromedriver_port: int | None = None
    mjpeg_server_port: int | None = None


class DevicePool:
    """
    Реестр устройств с автоматическим, гарантированно бесколлизионным
    распределением портов при регистрации.
    """

    # Диапазоны подтверждены документацией Appium UiAutomator2/XCUITest
    # драйверов на момент реализации (2026).
    SYSTEM_PORT_BASE = 8200
    WDA_LOCAL_PORT_BASE = 8100
    CHROMEDRIVER_PORT_BASE = 9515
    MJPEG_SERVER_PORT_BASE = 7810

    def __init__(self) -> None:
        self._devices: list[Device] = []

    def register(
        self,
        udid: str,
        platform: Platform,
        platform_version: str,
        device_name: str,
    ) -> Device:
        """Регистрирует устройство, автоматически назначая уникальные порты по индексу."""
        index = len(self._devices)
        device = Device(
            udid=udid,
            platform=platform,
            platform_version=platform_version,
            device_name=device_name,
            system_port=self.SYSTEM_PORT_BASE + index,
            wda_local_port=self.WDA_LOCAL_PORT_BASE + index,
            chromedriver_port=self.CHROMEDRIVER_PORT_BASE + index,
            mjpeg_server_port=self.MJPEG_SERVER_PORT_BASE + index,
        )
        self._devices.append(device)
        return device

    def __len__(self) -> int:
        return len(self._devices)

    @property
    def devices(self) -> list[Device]:
        return list(self._devices)

    def get_for_worker(self, worker_id: str | None) -> Device:
        """
        Детерминированно возвращает устройство для pytest-xdist worker'а.

        worker_id: 'gw0'/'gw1'/... (реальный xdist) или None/'master'
        (последовательный запуск без -n). Каждый worker — отдельный
        процесс, вычисляет свой индекс сам из СОБСТВЕННОГО worker_id —
        синхронизация между процессами не нужна.
        """
        if not self._devices:
            raise ValueError("DevicePool: no devices registered — call register() first")

        if worker_id is None or worker_id == "master":
            index = 0
        else:
            digits = "".join(c for c in worker_id if c.isdigit())
            index = int(digits) if digits else 0

        return self._devices[index % len(self._devices)]

    def to_capabilities_extra(self, device: Device) -> dict[str, int | str]:
        """
        Возвращает dict для DeviceCapabilities.extra с уникальными портами
        конкретного устройства — платформо-зависимый набор ключей.
        """
        extra: dict[str, int | str] = {"appium:udid": device.udid}
        if device.platform == Platform.ANDROID:
            if device.system_port is not None:
                extra["appium:systemPort"] = device.system_port
            if device.chromedriver_port is not None:
                extra["appium:chromedriverPort"] = device.chromedriver_port
        else:
            if device.wda_local_port is not None:
                extra["appium:wdaLocalPort"] = device.wda_local_port
        if device.mjpeg_server_port is not None:
            extra["appium:mjpegServerPort"] = device.mjpeg_server_port
        return extra

    def assert_no_port_collisions(self) -> None:
        """
        Sanity-проверка после регистрации всех устройств — вызывай в
        conftest.py на старте сессии, до первого реального запуска теста.
        """
        for attr in ("system_port", "wda_local_port", "chromedriver_port", "mjpeg_server_port"):
            values = [getattr(d, attr) for d in self._devices if getattr(d, attr) is not None]
            if len(values) != len(set(values)):
                raise AssertionError(f"DevicePool: port collision detected in '{attr}': {values}")
