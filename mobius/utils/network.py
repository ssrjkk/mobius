"""Network simulation — throttle, offline, latency."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from mobius.logging_config import get_logger
from mobius.utils.driver_health import rethrow_if_driver_dead

logger = get_logger(__name__)


class NetworkProfile(str, Enum):
    WIFI = "wifi"
    LTE = "4g"
    THREE_G = "3g"
    TWO_G = "2g"
    OFFLINE = "offline"


@dataclass
class NetworkCondition:
    download_speed: int  # Kbps
    upload_speed: int  # Kbps
    latency: int  # ms
    loss: float = 0.0  # % packet loss (0.0-1.0)


PROFILES: dict[NetworkProfile, NetworkCondition] = {
    NetworkProfile.WIFI: NetworkCondition(download_speed=50_000, upload_speed=20_000, latency=5),
    NetworkProfile.LTE: NetworkCondition(download_speed=10_000, upload_speed=5_000, latency=50),
    NetworkProfile.THREE_G: NetworkCondition(download_speed=1_500, upload_speed=750, latency=100),
    NetworkProfile.TWO_G: NetworkCondition(download_speed=250, upload_speed=100, latency=300),
    NetworkProfile.OFFLINE: NetworkCondition(download_speed=0, upload_speed=0, latency=0, loss=1.0),
}


class NetworkSimulator:
    """
    Переключает сетевой профиль устройства.

    Все методы-команды возвращают True только когда драйвер принял команду без
    исключения: `current_profile` должен описывать реальное состояние устройства,
    а не намерение теста. Иначе «тест на 3G» или «тест в offline» проходит на
    полностью связном устройстве — зелёный прогон, который ничего не проверял.

    Реально доступны два разных механизма:
      - OFFLINE/онлайн — `set_network_connection` (bitmask), работает на
        Android-эмуляторе и устройстве;
      - скорости (WIFI/LTE/3G/2G) — троттлинг, который драйвер обязан
        применить сам. Если он его не поддерживает, set_profile() вернёт
        False и `current_profile` не изменится: проверять связность в этом
        случае бессмысленно, нужен внешний шейпер (tc/clash, Network Link
        Conditioner на macOS, настройки AVD).
    """

    def __init__(self, driver: Any) -> None:
        self._driver = driver
        self._current: NetworkProfile | None = None

    def set_profile(self, profile: NetworkProfile) -> bool:
        if profile == NetworkProfile.OFFLINE:
            applied = self.go_offline()
        else:
            if self._current == NetworkProfile.OFFLINE:
                # Любой профиль кроме OFFLINE подразумевает связь: без этого
                # выход из offline оставил бы устройство без сети.
                self.go_online()
            applied = self._apply(PROFILES[profile])
        if applied:
            self._current = profile
        else:
            logger.warning(
                "set_profile('%s'): command was rejected — current_profile stays '%s'",
                profile.value,
                self._current.value if self._current else None,
            )
        return bool(applied)

    def go_offline(self) -> bool:
        applied = self._set_connection(0, "go_offline")
        if applied:
            self._current = NetworkProfile.OFFLINE
        return applied

    def go_online(self) -> bool:
        applied = self._set_connection(6, "go_online")
        if applied:
            self._current = NetworkProfile.WIFI
        return applied

    def _set_connection(self, bitmask: int, caller: str) -> bool:
        try:
            self._driver.set_network_connection(bitmask)
            return True
        except Exception as e:
            rethrow_if_driver_dead(e)
            logger.warning(
                "%s: set_network_connection(%d) not supported by this driver — "
                "network profile is NOT applied: %s",
                caller,
                bitmask,
                e,
            )
            return False

    def _apply(self, condition: NetworkCondition) -> bool:
        try:
            self._driver.execute_script(
                "mobile: setNetworkSpeed",
                {
                    "download": condition.download_speed,
                    "upload": condition.upload_speed,
                },
            )
            return True
        except Exception as e:
            rethrow_if_driver_dead(e)
            logger.warning(
                "_apply: mobile: setNetworkSpeed not supported — bandwidth throttling "
                "is not an Appium command on this driver, so the profile was NOT "
                "applied (use an external shaper instead): %s",
                e,
            )
            return False

    @property
    def current_profile(self) -> NetworkProfile | None:
        return self._current

    @staticmethod
    def get_condition(profile: NetworkProfile) -> NetworkCondition:
        return PROFILES[profile]
