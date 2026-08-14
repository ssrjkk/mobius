"""
Universal Element Finder — app-agnostic поиск элементов.

Screen Objects (mobius/screens/) требуют знания конкретных локаторов
одного приложения. Этот finder работает эвристически на ЛЮБОМ Android/iOS
приложении — ищет кнопки/поля/тексты по общим паттернам платформы,
без предварительного знания структуры экрана.

Используется когда:
- Нужно быстро smoke-тестировать незнакомое приложение
- Screen Object для конкретного экрана ещё не написан
- Нужна fallback-стратегия если основной локатор не сработал
"""

from __future__ import annotations

from typing import Any

from appium.webdriver.common.appiumby import AppiumBy

from mobius.logging_config import get_logger
from mobius.utils.platform_info import is_ios

logger = get_logger(__name__)


class UniversalFinder:
    """App-agnostic поиск элементов по эвристикам платформы."""

    ANDROID_BUTTON_CLASSES = [
        "android.widget.Button",
        "android.widget.ImageButton",
        "androidx.appcompat.widget.AppCompatButton",
    ]
    ANDROID_INPUT_CLASSES = [
        "android.widget.EditText",
        "androidx.appcompat.widget.AppCompatEditText",
    ]
    IOS_BUTTON_TYPES = ["XCUIElementTypeButton"]
    IOS_INPUT_TYPES = ["XCUIElementTypeTextField", "XCUIElementTypeSecureTextField"]

    def __init__(self, driver: Any) -> None:
        self._driver = driver

    def find_by_text(self, text: str, exact: bool = False) -> Any:
        """Находит любой элемент содержащий текст — работает на Android и iOS."""
        if exact:
            xpath = f'//*[@text="{text}" or @label="{text}" or @name="{text}" or @value="{text}"]'
        else:
            xpath = (
                f'//*[contains(@text,"{text}") or contains(@label,"{text}") '
                f'or contains(@name,"{text}") or contains(@value,"{text}")]'
            )
        return self._driver.find_element(AppiumBy.XPATH, xpath)

    def find_all_by_text(self, text: str) -> list[Any]:
        xpath = (
            f'//*[contains(@text,"{text}") or contains(@label,"{text}") '
            f'or contains(@name,"{text}")]'
        )
        return list(self._driver.find_elements(AppiumBy.XPATH, xpath))

    def find_any_button(self) -> list[Any]:
        """Находит все кнопкоподобные элементы на текущем экране."""
        if is_ios(self._driver):
            cond = " or ".join(f'@type="{c}"' for c in self.IOS_BUTTON_TYPES)
        else:
            cond = " or ".join(f'@class="{c}"' for c in self.ANDROID_BUTTON_CLASSES)
        return list(self._driver.find_elements(AppiumBy.XPATH, f"//*[{cond}]"))

    def find_any_input(self) -> list[Any]:
        """Находит все текстовые поля ввода на текущем экране."""
        if is_ios(self._driver):
            cond = " or ".join(f'@type="{c}"' for c in self.IOS_INPUT_TYPES)
        else:
            cond = " or ".join(f'@class="{c}"' for c in self.ANDROID_INPUT_CLASSES)
        return list(self._driver.find_elements(AppiumBy.XPATH, f"//*[{cond}]"))

    def find_button_by_text(self, text: str) -> Any:
        """Находит конкретную кнопку по видимому тексту/label — частый AQA кейс."""
        buttons = self.find_any_button()
        for b in buttons:
            label = (
                b.get_attribute("text")
                or b.get_attribute("label")
                or b.get_attribute("name")
                or b.get_attribute("content-desc")
                or ""
            )
            if text.lower() in label.lower():
                return b
        raise ValueError(f"Button with text '{text}' not found among {len(buttons)} buttons")

    def get_all_texts_on_screen(self) -> list[str]:
        """Весь видимый текст на экране — для быстрых smoke-проверок содержимого."""
        elements = self._driver.find_elements(
            AppiumBy.XPATH, "//*[@text!='' or @label!='' or @value!='']"
        )
        texts = []
        for e in elements:
            t = (
                e.get_attribute("text")
                or e.get_attribute("label")
                or e.get_attribute("value")
                or ""
            )
            if t:
                texts.append(t)
        return texts

    def screen_contains_text(self, text: str) -> bool:
        """Быстрая проверка присутствия текста где-либо на экране."""
        try:
            self.find_by_text(text)
            return True
        except Exception as e:
            logger.debug("screen_contains_text('%s'): not found: %s", text, e)
            return False
