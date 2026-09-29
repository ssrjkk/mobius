"""Unit tests — WaitUtils + RetryDecorator."""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)

from mobius.utils.retry_config import is_infrastructure_error
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
        with pytest.raises(TimeoutException):
            self.w.wait_for_condition(lambda: False, timeout=1, poll_frequency=0.1)

    def test_condition_timeout_is_not_builtin(self):
        """
        Должно быть именно selenium-исключение: на него настроен
        `--only-rerun=TimeoutException` в pyproject. Голый встроенный
        TimeoutError не попадал ни в rerun-фильтр, ни в классификацию
        retry_config, и инфраструктурный таймаут валил прогон как баг.
        """
        with pytest.raises(TimeoutException) as exc_info:
            self.w.wait_for_condition(lambda: False, timeout=1, poll_frequency=0.1)
        assert not isinstance(exc_info.value, TimeoutError)
        assert is_infrastructure_error(exc_info.value) is True

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

    def test_real_error_survives_optimized_mode(self, tmp_path):
        """
        Регрессия на `assert last_exc is not None`: под `python -O` assert
        исчезает, и `raise None` давало `TypeError: exceptions must derive
        from BaseException` вместо настоящей ошибки.
        """
        script = tmp_path / "retry_under_O.py"
        script.write_text(
            "from selenium.common.exceptions import StaleElementReferenceException\n"
            "from mobius.utils.wait_utils import RetryDecorator\n"
            "@RetryDecorator.retry(times=2, delay=0)\n"
            "def f():\n"
            "    raise StaleElementReferenceException('настоящая ошибка')\n"
            "try:\n"
            "    f()\n"
            "except StaleElementReferenceException:\n"
            "    print('OK_STALE')\n"
            "except BaseException as e:\n"
            "    print('BAD', type(e).__name__, e)\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, "-O", str(script)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert "OK_STALE" in result.stdout, f"stdout={result.stdout!r} stderr={result.stderr!r}"
