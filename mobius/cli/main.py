"""
mobius CLI — точка входа для `mobius doctor` и других команд.

Регистрируется как console_script в pyproject.toml:
    [project.scripts]
    mobius = "mobius.cli.main:main"

После pip install доступно как обычная shell-команда: `mobius doctor`.
"""

from __future__ import annotations

import argparse
import sys

from mobius.cli.diagnostics import Status, run_diagnostics

STATUS_SYMBOLS = {
    Status.OK: "✓",
    Status.WARNING: "!",
    Status.MISSING: "✗",
    Status.NOT_APPLICABLE: "-",
}


def cmd_doctor(args: argparse.Namespace) -> int:
    """
    Проверяет окружение: Python, mobius, зависимости, Appium сервер,
    adb, iOS simctl, ENV переменные. Возвращает 0 если критичных проблем
    нет (WARNING допустим — не блокирует), 1 если есть MISSING.
    """
    print("mobius doctor — проверка окружения\n")

    results = run_diagnostics(appium_url=args.appium_url)

    max_name_len = max(len(r.name) for r in results)
    for r in results:
        symbol = STATUS_SYMBOLS[r.status]
        print(f"  {symbol} {r.name.ljust(max_name_len)}  {r.detail}")

    blocking = [r for r in results if r.is_blocking]
    print()
    if blocking:
        print(f"✗ {len(blocking)} блокирующих проблем — UI тесты не запустятся:")
        for r in blocking:
            print(f"    - {r.name}: {r.detail}")
        return 1

    warnings = [r for r in results if r.status == Status.WARNING]
    if warnings:
        print(f"! {len(warnings)} предупреждений — не блокируют, но стоит проверить")
    else:
        print("✓ Всё готово")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mobius", description="Mobius mobile QA framework CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser(
        "doctor", help="Проверить окружение перед запуском UI тестов"
    )
    doctor_parser.add_argument(
        "--appium-url",
        default="http://localhost:4723",
        help="URL Appium сервера для проверки (default: http://localhost:4723)",
    )
    doctor_parser.set_defaults(func=cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
