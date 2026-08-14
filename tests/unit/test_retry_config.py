"""Unit tests — mobius.utils.retry_config."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mobius.utils.retry_config import (
    REAL_FAILURE_EXCEPTIONS,
    RetryConfig,
    configure_rerun_filter,
    is_infrastructure_error,
    pytest_flaky_report,
)

REPO_ROOT = Path(__file__).parent.parent.parent


@pytest.mark.unit
class TestIsInfrastructureError:
    def test_assertion_error_is_not_infrastructure(self):
        assert is_infrastructure_error(AssertionError("bad state")) is False

    def test_value_error_is_not_infrastructure(self):
        assert is_infrastructure_error(ValueError("bad input")) is False

    def test_timeout_error_is_infrastructure(self):
        assert is_infrastructure_error(TimeoutError("Appium timeout")) is True

    def test_connection_reset_is_infrastructure(self):
        assert is_infrastructure_error(ConnectionResetError("reset")) is True

    def test_unknown_exception_with_timeout_keyword_is_infrastructure(self):
        class CustomError(Exception):
            pass

        assert is_infrastructure_error(CustomError("operation timeout exceeded")) is True

    def test_unknown_exception_without_keyword_is_not_infrastructure(self):
        class CustomError(Exception):
            pass

        assert is_infrastructure_error(CustomError("something unrelated happened")) is False

    def test_stale_keyword_detected(self):
        class CustomError(Exception):
            pass

        assert is_infrastructure_error(CustomError("element is stale")) is True


@pytest.mark.unit
class TestRetryConfig:
    def test_initial_attempt_is_zero(self):
        retry = RetryConfig()
        assert retry.attempt == 0

    def test_record_attempt_increments(self):
        retry = RetryConfig()
        retry.record_attempt()
        assert retry.attempt == 1

    def test_should_retry_true_for_infra_error_within_limit(self):
        retry = RetryConfig(max_retries=2)
        assert retry.should_retry(TimeoutError()) is True

    def test_should_retry_false_for_real_failure(self):
        retry = RetryConfig(max_retries=2)
        assert retry.should_retry(AssertionError()) is False

    def test_should_retry_false_after_max_retries_reached(self):
        retry = RetryConfig(max_retries=1)
        retry.record_attempt()
        assert retry.should_retry(TimeoutError()) is False

    def test_last_exception_tracked(self):
        retry = RetryConfig()
        exc = TimeoutError("test")
        retry.record_attempt(exc)
        assert retry.last_exception is exc

    def test_reset_clears_state(self):
        retry = RetryConfig()
        retry.record_attempt(ValueError("x"))
        retry.reset()
        assert retry.attempt == 0
        assert retry.last_exception is None

    def test_default_max_retries_is_two(self):
        retry = RetryConfig()
        assert retry.max_retries == 2

    def test_default_delay_is_two_seconds(self):
        retry = RetryConfig()
        assert retry.delay_seconds == 2.0


@pytest.mark.unit
class TestPytestFlakyReport:
    def test_infrastructure_error_labeled_correctly(self):
        report = pytest_flaky_report(TimeoutError("Appium slow"))
        assert "INFRASTRUCTURE" in report
        assert "TimeoutError" in report

    def test_real_failure_labeled_correctly(self):
        report = pytest_flaky_report(AssertionError("wrong value"))
        assert "REAL_FAILURE" in report

    def test_message_truncated_to_200_chars(self):
        long_msg = "x" * 500
        report = pytest_flaky_report(ValueError(long_msg))
        assert len(report) < 250


@pytest.mark.unit
class TestConfigureRerunFilter:
    def test_sets_rerun_except_on_config(self):
        config = MagicMock()
        configure_rerun_filter(config)
        assert config.option.rerun_except == list(REAL_FAILURE_EXCEPTIONS)

    def test_rerun_except_contains_assertion_error(self):
        config = MagicMock()
        configure_rerun_filter(config)
        assert "AssertionError" in config.option.rerun_except

    def test_rerun_except_is_a_list_not_tuple(self):
        """pytest-rerunfailures action='append' produces a list, не tuple."""
        config = MagicMock()
        configure_rerun_filter(config)
        assert isinstance(config.option.rerun_except, list)


@pytest.mark.unit
class TestConfigureRerunFilterRealIntegration:
    """
    Реальная (не mock) проверка — спавним настоящий pytest subprocess
    с настоящим pytest-rerunfailures, доказываем что AssertionError НЕ
    ретраится, а TimeoutError ретраится до успеха. Mock-тесты выше
    проверяют что мы ПРАВИЛЬНО вызываем API; этот тест проверяет что
    сам API делает то, что мы думаем — тот же принцип что и
    tests/wire_protocol/ для Appium-стороны.
    """

    def test_assertion_error_not_rerun_real_subprocess(self, tmp_path):
        import subprocess
        import sys

        conftest = tmp_path / "conftest.py"
        conftest.write_text(
            "import sys\n"
            f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
            "from mobius.utils.retry_config import configure_rerun_filter\n"
            "def pytest_configure(config):\n"
            "    configure_rerun_filter(config)\n"
        )
        test_file = tmp_path / "test_real_bug.py"
        test_file.write_text("def test_fails():\n    assert False, 'genuine bug'\n")

        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "--reruns", "3", "-v"],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            timeout=30,
        )
        assert "RERUN" not in result.stdout, (
            f"AssertionError should NOT trigger rerun:\n{result.stdout}"
        )
        assert "1 failed" in result.stdout

    def test_timeout_error_is_rerun_real_subprocess(self, tmp_path):
        import subprocess
        import sys

        conftest = tmp_path / "conftest.py"
        conftest.write_text(
            "import sys\n"
            f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
            "from mobius.utils.retry_config import configure_rerun_filter\n"
            "def pytest_configure(config):\n"
            "    configure_rerun_filter(config)\n"
        )
        counter_file = tmp_path / "attempts.txt"
        test_file = tmp_path / "test_flaky.py"
        test_file.write_text(
            f"COUNTER = {str(counter_file)!r}\n"
            "import os\n"
            "def test_flaky():\n"
            "    count = int(open(COUNTER).read()) if os.path.exists(COUNTER) else 0\n"
            "    count += 1\n"
            "    open(COUNTER, 'w').write(str(count))\n"
            "    if count < 3:\n"
            "        raise TimeoutError('simulated Appium timeout')\n"
            "    assert True\n"
        )

        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "--reruns", "3", "-v"],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            timeout=30,
        )
        assert "RERUN" in result.stdout, f"TimeoutError SHOULD trigger rerun:\n{result.stdout}"
        assert "1 passed" in result.stdout
