"""
Unit tests — `mobius/utils/driver_health.py`.

Best-effort предикаты framework'а (`is_displayed`, `screen_contains_text`,
`get_logs`, …) по контракту возвращают False когда элемента нет. Если в тот
же `except Exception` попадает и мёртвый Appium, инфраструктурный провал
выглядит как «элемента нет» и прогон становится зелёным без единого шага.
Вся разница в мире держится на этом модуле — поэтому он покрыт напрямую,
а не только через вызывающие его хелперы.
"""

from __future__ import annotations

import pytest
from selenium.common.exceptions import (
    InvalidSelectorException,
    InvalidSessionIdException,
    NoSuchElementException,
    SessionNotCreatedException,
    TimeoutException,
    WebDriverException,
)

from mobius.utils.driver_health import is_driver_dead, rethrow_if_driver_dead


def _wd(msg: str) -> WebDriverException:
    """WebDriverException с сообщением — ровно то, в чём Selenium приезжает
    на транспортные и session-level сбои (отдельного класса у них нет)."""
    return WebDriverException(msg=msg)


@pytest.mark.unit
class TestIsDriverDead:
    @pytest.mark.parametrize(
        "exc",
        [
            InvalidSessionIdException("Session does not exist"),
            SessionNotCreatedException("Unable to create new session"),
            OSError("[Errno 111] Connection refused"),
            ConnectionResetError("connection reset"),
            TimeoutError("timed out"),
        ],
    )
    def test_fatal_classes_are_detected(self, exc):
        assert is_driver_dead(exc) is True

    @pytest.mark.parametrize(
        "msg",
        [
            "invalid session id 'abc123'",
            "no such session found",
            "'07e5f9d' is not registered with the scheduler",
            "session has expired",
            "session closed due to inactivity",
            "Max retries exceeded with url: /wd/hub/session",
            "Failed to establish a new connection",
            "Connection refused",
            "ECONNREFUSED 127.0.0.1:4723",
            "('Connection aborted.', RemoteDisconnected(...))",
            "Remote end closed connection without response",
            "returned status 503: target machine refused connection",
        ],
    )
    def test_fatal_messages_wrapped_in_generic_exception_are_detected(self, msg):
        assert is_driver_dead(_wd(msg)) is True

    @pytest.mark.parametrize(
        "exc",
        [
            NoSuchElementException("Ability to login is not found"),
            InvalidSelectorException("An invalid selector was used"),
            TimeoutException("timed out after 10000ms"),
            _wd("An unknown server-side error occurred"),
            _wd("chrome not reachable: session is not a chrome session"),
            ValueError("bad argument"),
            KeyError("missing"),
            RuntimeError("boom"),
        ],
    )
    def test_ordinary_negatives_stay_ordinary(self, exc):
        """«Элемента нет» — штатный результат, он не должен ронять прогон."""
        assert is_driver_dead(exc) is False

    def test_cause_chain_is_inspected(self):
        """urllib3/requests заворачивают сетевую ошибку в голый WebDriverException."""

        def raise_wrapped() -> None:
            try:
                raise OSError("[Errno 10054] Remote host closed the connection")
            except OSError as transport:
                raise WebDriverException(msg="POST /session didn't answer in time") from transport

        with pytest.raises(WebDriverException) as caught:
            raise_wrapped()
        exc = caught.value
        assert is_driver_dead(exc) is True


@pytest.mark.unit
class TestRethrowIfDriverDead:
    def test_fatal_error_propagates(self):
        exc = InvalidSessionIdException("Session does not exist")
        with pytest.raises(InvalidSessionIdException):
            rethrow_if_driver_dead(exc)

    def test_non_fatal_error_is_left_alone(self):
        rethrow_if_driver_dead(NoSuchElementException("not there"))

    def test_oserror_propagates(self):
        with pytest.raises(ConnectionResetError):
            rethrow_if_driver_dead(ConnectionResetError("reset"))
