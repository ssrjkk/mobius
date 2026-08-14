"""Network simulation — throttle, offline, latency."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from mobius.logging_config import get_logger

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
    def __init__(self, driver: Any) -> None:
        self._driver = driver
        self._current: NetworkProfile | None = None

    def set_profile(self, profile: NetworkProfile) -> None:
        self._current = profile
        if profile == NetworkProfile.OFFLINE:
            self.go_offline()
        else:
            self._apply(PROFILES[profile])

    def go_offline(self) -> None:
        self._current = NetworkProfile.OFFLINE
        try:
            self._driver.set_network_connection(0)
        except Exception as e:
            logger.warning(
                "go_offline: set_network_connection(0) not supported by this "
                "driver — network profile tracked in-memory only: %s",
                e,
            )

    def go_online(self) -> None:
        self._current = NetworkProfile.WIFI
        try:
            self._driver.set_network_connection(6)
        except Exception as e:
            logger.warning(
                "go_online: set_network_connection(6) not supported by this driver: %s",
                e,
            )

    def _apply(self, condition: NetworkCondition) -> None:
        try:
            self._driver.execute_script(
                "mobile: setNetworkSpeed",
                {
                    "download": condition.download_speed,
                    "upload": condition.upload_speed,
                },
            )
        except Exception as e:
            logger.warning(
                "_apply: mobile: setNetworkSpeed not supported — this command "
                "requires a real device with network shaping (not all "
                "emulators/simulators support it): %s",
                e,
            )

    @property
    def current_profile(self) -> NetworkProfile | None:
        return self._current

    @staticmethod
    def get_condition(profile: NetworkProfile) -> NetworkCondition:
        return PROFILES[profile]
