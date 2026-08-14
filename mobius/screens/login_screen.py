"""Login Screen — Sauce Labs Demo App (https://github.com/saucelabs/my-demo-app-rn)."""

from __future__ import annotations

from appium.webdriver.common.appiumby import AppiumBy

from mobius.screens.base_screen import BaseScreen


class LoginScreen(BaseScreen):
    _USERNAME = (AppiumBy.ACCESSIBILITY_ID, "Username input field")
    _PASSWORD = (AppiumBy.ACCESSIBILITY_ID, "Password input field")
    _LOGIN_BTN = (AppiumBy.ACCESSIBILITY_ID, "Login button")
    _ERROR_MSG = (AppiumBy.XPATH, '//*[@content-desc="generic-error-message"]')
    _BIOMETRICS = (AppiumBy.ACCESSIBILITY_ID, "Login with Biometrics button")

    @property
    def is_open(self) -> bool:
        return self.is_element_present(self._LOGIN_BTN, timeout=5)

    def enter_username(self, username: str) -> LoginScreen:
        self.type_text(self._USERNAME, username)
        return self

    def enter_password(self, password: str) -> LoginScreen:
        self.type_text(self._PASSWORD, password)
        self.hide_keyboard()
        return self

    def tap_login(self) -> None:
        self.tap(self._LOGIN_BTN)

    def login(self, username: str, password: str) -> None:
        """Полный flow логина."""
        self.enter_username(username).enter_password(password).tap_login()

    def get_error_message(self) -> str:
        return self.get_text(self._ERROR_MSG)

    def is_error_shown(self) -> bool:
        return self.is_element_present(self._ERROR_MSG, timeout=3)

    def tap_biometrics(self) -> None:
        self.tap(self._BIOMETRICS)
