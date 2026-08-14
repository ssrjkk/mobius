"""
Централизованная настройка логирования Mobius.

Все universal-модули (device, alerts, gestures, network, ...) используют
best-effort паттерн: если Appium команда не поддерживается на конкретном
драйвере/платформе, метод возвращает False/None/[] вместо падения теста.

Раньше это делалось через голый `except Exception: return False` — команда
в CI получала молчаливый провал без единой подсказки почему. Теперь каждый
такой fallback пишет WARNING в лог с именем модуля, что попробовали сделать
и что пошло не так.

Использование в коде Mobius:
    from mobius.logging_config import get_logger
    logger = get_logger(__name__)
    ...
    except Exception:
        logger.warning("rotate_to_landscape failed: driver doesn't support orientation")
        return False

Настройка уровня логирования командой (проектом-потребителем):
    import logging
    logging.getLogger("mobius").setLevel(logging.DEBUG)
"""

from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def _configure_once() -> None:
    """Настраивает root-логгер Mobius один раз при первом использовании."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger("mobius")
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        root.addHandler(handler)
        root.setLevel(logging.WARNING)  # по умолчанию видны только WARNING+
        root.propagate = False  # не дублируем в root-логгер приложения-потребителя

    _CONFIGURED = True


def get_logger(module_name: str) -> logging.Logger:
    """
    Возвращает логгер для модуля Mobius.
    module_name обычно — __name__ вызывающего модуля
    (например 'mobius.utils.device').
    """
    _configure_once()
    return logging.getLogger(module_name)


def set_level(level: int) -> None:
    """
    Меняет уровень логирования Mobius. Команда может вызвать
    set_level(logging.DEBUG) в conftest.py чтобы видеть все best-effort
    попытки, не только провалившиеся.
    """
    _configure_once()
    logging.getLogger("mobius").setLevel(level)
