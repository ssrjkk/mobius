"""Unit tests — mobius.cli.diagnostics и mobius.cli.main."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from mobius.cli.diagnostics import (
    CheckResult,
    Status,
    check_adb,
    check_appium_server,
    check_core_dependencies,
    check_env_vars,
    check_ios_simctl,
    check_mobius_version,
    check_python_version,
    has_blocking_issues,
    run_diagnostics,
)
from mobius.cli.main import build_parser, cmd_doctor, main


@pytest.mark.unit
class TestCheckPythonVersion:
    def test_current_python_is_ok(self):
        """Тест сам исполняется на Python >=3.12 (requires-python в pyproject.toml)."""
        result = check_python_version()
        assert result.status == Status.OK

    def test_old_python_gives_warning(self):
        with patch.object(sys, "version_info", (3, 10, 0, "final", 0)):
            result = check_python_version()
        assert result.status == Status.WARNING
        assert "3.10" in result.detail


@pytest.mark.unit
class TestCheckMobiusVersion:
    def test_returns_ok_with_version_string(self):
        result = check_mobius_version()
        assert result.status == Status.OK
        assert result.detail  # непустая строка версии


@pytest.mark.unit
class TestCheckCoreDependencies:
    def test_all_installed_returns_ok(self):
        result = check_core_dependencies()
        assert result.status == Status.OK

    def test_missing_dependency_returns_missing(self):
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "PIL":
                raise ImportError("No module named 'PIL'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            result = check_core_dependencies()
        assert result.status == Status.MISSING
        assert "PIL" in result.detail


@pytest.mark.unit
class TestCheckAppiumServer:
    def test_reachable_server_returns_ok(self):
        with patch("mobius.cli.diagnostics.is_appium_available", return_value=True):
            result = check_appium_server()
        assert result.status == Status.OK

    def test_unreachable_server_returns_warning(self):
        with patch("mobius.cli.diagnostics.is_appium_available", return_value=False):
            result = check_appium_server()
        assert result.status == Status.WARNING
        assert "appium --base-path" in result.detail

    def test_uses_custom_url(self):
        with patch("mobius.cli.diagnostics.is_appium_available", return_value=True) as m:
            check_appium_server(url="http://custom:9999")
        m.assert_called_once_with("http://custom:9999")


@pytest.mark.unit
class TestCheckAdb:
    def test_adb_not_found_returns_missing(self):
        with patch("shutil.which", return_value=None):
            result = check_adb()
        assert result.status == Status.MISSING
        assert result.is_blocking is True

    def test_adb_found_and_runs_returns_ok(self):
        with (
            patch("shutil.which", return_value="/usr/bin/adb"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(stdout="Android Debug Bridge version 1.0.41\n")
            result = check_adb()
        assert result.status == Status.OK
        assert "/usr/bin/adb" in result.detail

    def test_adb_found_but_version_fails_returns_warning(self):
        with (
            patch("shutil.which", return_value="/usr/bin/adb"),
            patch("subprocess.run", side_effect=Exception("timeout")),
        ):
            result = check_adb()
        assert result.status == Status.WARNING


@pytest.mark.unit
class TestCheckIosSimctl:
    def test_non_macos_returns_not_applicable(self):
        with patch("platform.system", return_value="Linux"):
            result = check_ios_simctl()
        assert result.status == Status.NOT_APPLICABLE
        assert result.is_blocking is False

    def test_macos_with_xcrun_returns_ok(self):
        with (
            patch("platform.system", return_value="Darwin"),
            patch("shutil.which", return_value="/usr/bin/xcrun"),
        ):
            result = check_ios_simctl()
        assert result.status == Status.OK

    def test_macos_without_xcrun_returns_missing(self):
        with (
            patch("platform.system", return_value="Darwin"),
            patch("shutil.which", return_value=None),
        ):
            result = check_ios_simctl()
        assert result.status == Status.MISSING


@pytest.mark.unit
class TestCheckEnvVars:
    def test_set_var_returns_ok(self, monkeypatch):
        monkeypatch.setenv("APP_PATH", "/path/to/app.apk")
        results = check_env_vars()
        app_path_result = next(r for r in results if "APP_PATH" in r.name)
        assert app_path_result.status == Status.OK
        assert app_path_result.detail == "/path/to/app.apk"

    def test_unset_var_returns_warning(self, monkeypatch):
        monkeypatch.delenv("APP_PACKAGE", raising=False)
        results = check_env_vars()
        result = next(r for r in results if "APP_PACKAGE" in r.name)
        assert result.status == Status.WARNING

    def test_env_vars_never_block(self, monkeypatch):
        for var in ("APP_PATH", "APP_PACKAGE", "DEVICE_UDID", "DEVICE_NAME"):
            monkeypatch.delenv(var, raising=False)
        results = check_env_vars()
        assert not any(r.is_blocking for r in results)


@pytest.mark.unit
class TestRunDiagnostics:
    def test_returns_nonempty_list(self):
        results = run_diagnostics()
        assert len(results) >= 6

    def test_all_results_are_check_result_instances(self):
        results = run_diagnostics()
        assert all(isinstance(r, CheckResult) for r in results)

    def test_custom_appium_url_propagates(self):
        with patch("mobius.cli.diagnostics.is_appium_available", return_value=False) as m:
            run_diagnostics(appium_url="http://custom:1234")
        m.assert_called_once_with("http://custom:1234")


@pytest.mark.unit
class TestHasBlockingIssues:
    def test_no_blocking_returns_false(self):
        results = [
            CheckResult("a", Status.OK, ""),
            CheckResult("b", Status.WARNING, ""),
            CheckResult("c", Status.NOT_APPLICABLE, ""),
        ]
        assert has_blocking_issues(results) is False

    def test_missing_returns_true(self):
        results = [
            CheckResult("a", Status.OK, ""),
            CheckResult("b", Status.MISSING, ""),
        ]
        assert has_blocking_issues(results) is True

    def test_empty_list_returns_false(self):
        assert has_blocking_issues([]) is False


@pytest.mark.unit
class TestCmdDoctor:
    def test_no_blocking_returns_zero(self, capsys):
        fake_results = [
            CheckResult("Python", Status.OK, "3.12"),
            CheckResult("Appium", Status.WARNING, "not running"),
        ]
        with patch("mobius.cli.main.run_diagnostics", return_value=fake_results):
            args = MagicMock(appium_url="http://localhost:4723")
            exit_code = cmd_doctor(args)
        assert exit_code == 0

    def test_blocking_returns_one(self, capsys):
        fake_results = [
            CheckResult("adb", Status.MISSING, "not found"),
        ]
        with patch("mobius.cli.main.run_diagnostics", return_value=fake_results):
            args = MagicMock(appium_url="http://localhost:4723")
            exit_code = cmd_doctor(args)
        assert exit_code == 1

    def test_prints_all_check_names(self, capsys):
        fake_results = [
            CheckResult("Custom Check Name", Status.OK, "detail here"),
        ]
        with patch("mobius.cli.main.run_diagnostics", return_value=fake_results):
            args = MagicMock(appium_url="http://localhost:4723")
            cmd_doctor(args)
        captured = capsys.readouterr()
        assert "Custom Check Name" in captured.out
        assert "detail here" in captured.out


@pytest.mark.unit
class TestBuildParser:
    def test_doctor_subcommand_parses(self):
        parser = build_parser()
        args = parser.parse_args(["doctor"])
        assert args.command == "doctor"
        assert args.appium_url == "http://localhost:4723"

    def test_doctor_custom_appium_url(self):
        parser = build_parser()
        args = parser.parse_args(["doctor", "--appium-url", "http://example.com:1234"])
        assert args.appium_url == "http://example.com:1234"

    def test_no_command_raises(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])


@pytest.mark.unit
class TestMainEntrypoint:
    def test_main_doctor_returns_int(self):
        fake_results = [CheckResult("x", Status.OK, "y")]
        with patch("mobius.cli.main.run_diagnostics", return_value=fake_results):
            result = main(["doctor"])
        assert result == 0

    def test_main_doctor_blocking_returns_one(self):
        fake_results = [CheckResult("adb", Status.MISSING, "not found")]
        with patch("mobius.cli.main.run_diagnostics", return_value=fake_results):
            result = main(["doctor"])
        assert result == 1
