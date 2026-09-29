# Security Policy

Mobius is a Python test framework for mobile QA (Appium 2.x + pytest). It is a
library and a CLI that runs inside a tester's own environment — it is not a
network service and does not store production data. It does, however, build
device shell commands and locator strings from configuration and test
parameters, which is treated as its real attack surface (see below).

## Supported versions

| Version      | Supported | Notes                                                          |
|--------------|-----------|----------------------------------------------------------------|
| 2.2.x        | Yes       | Current release line (`pyproject.toml` → `version = "2.2.0"`)   |
| older than 2.2 | No      | No backported fixes; please reproduce on 2.2.x first            |

Python: only the versions allowed by `requires-python = ">=3.12"` in
`pyproject.toml` are supported (3.12 and later). Appium 2.x WebDriver servers
only. Reports that reproduce solely on Python ≤ 3.11 or on an Appium 1.x server
are out of scope.

## Reporting a vulnerability

Please use **private vulnerability reporting** through GitHub, not a public
issue and not a pull request:

<https://github.com/ssrjkk/mobius/security/advisories/new>

If private vulnerability reporting is unavailable on this repository, open an
issue titled `security: disclosure request` and wait for the maintainer to
reply before describing the problem — the issue body must not contain the
vulnerability details.

There is no separate security mailing list; anything other than the GitHub
advisory thread is not an official channel.

Helpful in a report:

- Mobius version and Python version, Appium server version, OS/device/emulator.
- Whether the issue is in the library code, a bundled example/config, or a
  dependency.
- A minimal reproducer (test snippet or CLI command) and the observed impact.
- Which inputs an attacker would have to control (YAML config, test parameter,
  device name, deep link, server response, …).

### Response times

| Milestone                                             | Target        |
|-------------------------------------------------------|---------------|
| Acknowledgement of the report                         | 3 days        |
| Reproduction and severity assessment                  | 7 days        |
| Fix released or a written decision, Critical/High      | 30 days       |
| Fix released or a written decision, Medium/Low         | 60 days       |

These are best-effort targets for a single-maintainer project, not a contractual
SLA. Please do not publish details until a fix is available or 90 days have
passed, whichever comes first — say so in the report if you plan to disclose
earlier.

## What we consider a vulnerability

- Code execution, path traversal or command injection reachable from inputs a
  Mobius user does not control (Appium/cloud server responses, YAML configs from
  third parties, artifacts pulled off a device).
- Credential or secret leakage into `reports/`, `allure-results/`, logs,
  screenshots or video recorded by the framework.
- Deserialization of untrusted YAML/pickle payloads through this project's own
  config loading.
- SSRF or unencrypted transport in the built-in cloud-provider and
  Appium-server client code.
- A `--strict`/`nosec`/lint suppression added in this repository that hides a
  real finding.

### Attack surface of a test framework

Most findings in a project like this come from data crossing a boundary it was
not designed to defend. In Mobius the boundaries to examine are:

1. **Device shell commands** — helpers that call `mobile: shell` / the emulator
   console (`mobius/utils/accessibility.py`, `mobius/utils/interruptions.py`)
   and diagnostics that shell out to `adb`. Any value that reaches those
   argument lists is a command-injection candidate.
2. **Locator strings** — XPath and other locators assembled from test data or
   YAML (`mobius/utils/xpath.py`, `mobius/elements/`, `mobius/screens/`) are
   interpreted by UIAutomator2 / XCUITest, so escaping of literal values
   matters.
3. **Configuration and app data** — `pyyaml`-parsed per-application configs and
   everything under `apps/` and `devices/`.
4. **Deep links, clipboard and file transfer** — `mobius/utils/deeplink.py`,
   `mobius/utils/clipboard.py`, `mobius/utils/file_transfer.py` move data
   in and out of a device, including off-device paths.
5. **HTTP to the Appium server and cloud providers** — `mobius/driver/`,
   `mobius/utils/cloud_providers.py`: base URLs, auth headers, response bodies.
6. **Artifacts** — `reports/`, screenshots, screen recordings and device logs
   can capture PII or session tokens from the app under test.

## Out of scope

- Vulnerabilities in upstream dependencies (Appium-Python-Client, selenium,
  requests, Pillow, pytest, …). Report those to the upstream project; Mobius
  tracks them with Dependabot security updates and `pip-audit`, and bumps the
  requirement once a fixed release exists.
- Issues in Appium server, UiAutomator2/XCUITest drivers, `adb`, emulators, the
  device OS or the app under test.
- Anything that requires the attacker to already control the tester's machine,
  device, CI runner or git repository.
- Misuse of the library by test code the user writes: Mobius is a library, so
  code passing untrusted values into its shell/locator helpers is the caller's
  trust boundary unless the framework documents those values as safe.
- Findings from automated scanners with no demonstrated impact, and findings in
  test fixtures or examples that never run against a real target.
- Cloud-provider account problems, social engineering, spam/DoS, missing
  best-practice headers on documentation pages.

## How this repository is checked

- `make security` runs `bandit` (SAST, configured in `pyproject.toml` under
  `[tool.bandit]`) and `pip-audit` for known dependency CVEs.
- `.github/workflows/codeql.yml` runs CodeQL for Python source and for the
  workflow files themselves on every push to `main`, every pull request and on a
  weekly schedule.
- `.github/dependabot.yml` opens update pull requests for Python dependencies
  and GitHub Actions; Dependabot security updates additionally alert on
  vulnerable requirements.
- `pyproject.toml` pins the supported Python floor (`>=3.12`) and the lint/type
  gates (ruff, mypy `strict`) that CI enforces.
