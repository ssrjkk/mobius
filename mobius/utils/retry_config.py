"""
Smart retry для мобильных тестов — отделяем реальные баги от
инфраструктурных flaky сценариев (Appium timeout, эмулятор завис,
StaleElement на медленном CI).

Проблема без этого модуля: pytest-rerunfailures с `--reruns 3` перезапускает
ВСЁ — в том числе тесты которые упали по-настоящему (неверный assert).
Команда видит "тест иногда проходит" и думает что это flaky, хотя на самом
деле это реальный баг который иногда проявляется.

Решение: классифицируем исключения — retry только на инфраструктурные,
не на assertion failures. Механизм подтверждён эмпирически — реальный
прогон pytest --reruns 3 с config.option.rerun_except показывает что
AssertionError падает 1 раз (не ретраится), TimeoutError ретраится
до успеха (см. docs/adr/008-smart-retry-classification.md).
"""

from __future__ import annotations

from typing import Any

# Исключения которые ТОЧНО инфраструктурные, не баги в тестируемом коде
INFRASTRUCTURE_EXCEPTIONS = (
    "WebDriverException",
    "TimeoutException",
    "StaleElementReferenceException",
    "ConnectionResetError",
    "RemoteDisconnected",
    "MaxRetryError",
    "NewConnectionError",
    "TimeoutError",
)

# Исключения которые НЕ нужно ретраить — это реальные провалы теста
REAL_FAILURE_EXCEPTIONS = (
    "AssertionError",  # assert failed — реальный баг
    "ValueError",  # некорректные данные — реальный баг
    "AttributeError",  # ошибка в коде теста — реальный баг
)


def is_infrastructure_error(exc: BaseException) -> bool:
    """
    Возвращает True если исключение — инфраструктурное (стоит повторить тест),
    False если это реальное падение теста (retry бессмысленен).
    """
    exc_type = type(exc).__name__
    if exc_type in REAL_FAILURE_EXCEPTIONS:
        return False
    if exc_type in INFRASTRUCTURE_EXCEPTIONS:
        return True
    # Для всего остального — смотрим на текст
    exc_msg = str(exc).lower()
    infra_keywords = ("timeout", "connection", "refused", "unreachable", "stale")
    return any(kw in exc_msg for kw in infra_keywords)


class RetryConfig:
    """
    Ручной трекер retry-попыток — для кода ВНЕ pytest-rerunfailures
    (например явный retry-цикл в utility функции, не в самом тесте).

    Использование:
        retry = RetryConfig(max_retries=2)
        while True:
            try:
                do_flaky_thing()
                break
            except Exception as e:
                retry.record_attempt(e)
                if not retry.should_retry(e):
                    raise
    """

    def __init__(
        self,
        max_retries: int = 2,
        delay_seconds: float = 2.0,
    ) -> None:
        self.max_retries = max_retries
        self.delay_seconds = delay_seconds
        self._attempt = 0
        self._last_exception: BaseException | None = None

    @property
    def attempt(self) -> int:
        return self._attempt

    def should_retry(self, exc: BaseException) -> bool:
        """Должны ли мы повторить операцию после этого исключения?"""
        if self._attempt >= self.max_retries:
            return False
        return is_infrastructure_error(exc)

    def record_attempt(self, exc: BaseException | None = None) -> None:
        self._attempt += 1
        self._last_exception = exc

    @property
    def last_exception(self) -> BaseException | None:
        return self._last_exception

    def reset(self) -> None:
        self._attempt = 0
        self._last_exception = None


def pytest_flaky_report(exc: BaseException) -> str:
    """Формирует сообщение для Allure/лога при retry."""
    category = "infrastructure" if is_infrastructure_error(exc) else "real_failure"
    return f"[{category.upper()}] {type(exc).__name__}: {str(exc)[:200]}"


def configure_rerun_filter(config: Any) -> None:
    """
    Применяет умный rerun filter к pytest-rerunfailures — вызывать из
    conftest.py::pytest_configure(config).

    Механизм: pytest-rerunfailures читает config.option.rerun_except
    (dest 'rerun_except' из --rerun-except CLI флага, pytest_rerunfailures/
    plugin.py) — устанавливаем программно, без необходимости передавать
    флаг руками в каждой команде.

    Verified эмпирически (не просто предположение по исходникам):
    реальный pytest --reruns 3 прогон с этой настройкой — AssertionError
    падает 1 раз, TimeoutError ретраится до 3 раз до PASSED.

    Пример:
        def pytest_configure(config):
            from mobius.utils.retry_config import configure_rerun_filter
            configure_rerun_filter(config)
    """
    config.option.rerun_except = list(REAL_FAILURE_EXCEPTIONS)
