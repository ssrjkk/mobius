"""Unit tests — WaitUtils + RetryDecorator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException

from mobius.utils.wait_utils import RetryDecorator, WaitUtils


@pytest.mark.unit
class TestWaitUtils:
    def setup_method(self):
        self.d = MagicMock()
        self.w = WaitUtils(self.d, default_timeout=2)

    def test_condition_success(self):
        assert self.w.wait_for_condition(lambda: "ok") == "ok"

    def test_condition_retries_on_exception(self):
        calls = [0]

        def f():
            calls[0] += 1
            if calls[0] < 3:
                raise NoSuchElementException()
            return "found"

        assert self.w.wait_for_condition(f, poll_frequency=0.05) == "found"
        assert calls[0] == 3

    def test_condition_timeout(self):
        with pytest.raises(TimeoutError):
            self.w.wait_for_condition(lambda: False, timeout=1, poll_frequency=0.1)

    def test_condition_timeout_reraises_last_exception(self):
        with pytest.raises(NoSuchElementException):
            self.w.wait_for_condition(
                lambda: (_ for _ in ()).throw(NoSuchElementException()),
                timeout=1,
                poll_frequency=0.1,
            )

    def test_loading_gone_no_error_if_missing(self):
        self.w.wait_for_loading_gone(("id", "loader"), timeout=1)

    def test_wait_for_element_visible(self):
        mock_elem = MagicMock()
        with patch("mobius.utils.wait_utils.WebDriverWait") as W:
            W.return_value.until.return_value = mock_elem
            result = self.w.wait_for_element_visible(("id", "x"))
        assert result == mock_elem

    def test_wait_for_element_clickable(self):
        mock_elem = MagicMock()
        with patch("mobius.utils.wait_utils.WebDriverWait") as W:
            W.return_value.until.return_value = mock_elem
            result = self.w.wait_for_element_clickable(("id", "x"))
        assert result == mock_elem

    def test_wait_for_element_invisible(self):
        with patch("mobius.utils.wait_utils.WebDriverWait") as W:
            W.return_value.until.return_value = True
            assert self.w.wait_for_element_invisible(("id", "x")) is True

    def test_wait_for_text(self):
        with patch("mobius.utils.wait_utils.WebDriverWait") as W:
            W.return_value.until.return_value = True
            assert self.w.wait_for_text(("id", "x"), "hello") is True


@pytest.mark.unit
class TestRetryDecorator:
    def test_success_first_try(self):
        calls = [0]

        @RetryDecorator.retry(times=3)
        def f():
            calls[0] += 1
            return "ok"

        assert f() == "ok"
        assert calls[0] == 1

    def test_retries_on_stale(self):
        calls = [0]

        @RetryDecorator.retry(times=3, delay=0.01)
        def f():
            calls[0] += 1
            if calls[0] < 3:
                raise StaleElementReferenceException()
            return "recovered"

        assert f() == "recovered"
        assert calls[0] == 3

    def test_raises_after_max(self):
        @RetryDecorator.retry(times=2, delay=0.01)
        def f():
            raise StaleElementReferenceException()

        with pytest.raises(StaleElementReferenceException):
            f()

    def test_no_catch_other_exceptions(self):
        @RetryDecorator.retry(times=3)
        def f():
            raise ValueError("other")

        with pytest.raises(ValueError):
            f()


@pytest.mark.unit
class TestRetryDecoratorEdgeCase:
    """
    Регрессия: mypy поймал что raise last_exc мог выполниться с last_exc=None
    при times=0 (цикл range(0) не выполняется ни разу). Раньше это давало
    непонятный 'TypeError: exceptions must derive from BaseException' вместо
    внятной ошибки конфигурации.
    """

    def test_times_zero_raises_clear_value_error(self):
        with pytest.raises(ValueError, match="times must be >= 1"):

            @RetryDecorator.retry(times=0)
            def f():
                return "unreachable"

    def test_negative_times_raises_clear_value_error(self):
        with pytest.raises(ValueError, match="times must be >= 1"):

            @RetryDecorator.retry(times=-1)
            def f():
                return "unreachable"

    def test_times_one_still_works(self):
        calls = [0]

        @RetryDecorator.retry(times=1)
        def f():
            calls[0] += 1
            return "ok"

        assert f() == "ok"
        assert calls[0] == 1
