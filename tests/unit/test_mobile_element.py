"""Unit tests — MobileElement."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from selenium.common.exceptions import StaleElementReferenceException

from mobius.elements.mobile_element import MobileElement


@pytest.mark.unit
class TestMobileElement:
    def setup_method(self):
        self.d = MagicMock()
        self.e = MagicMock()
        self.elem = MobileElement(self.d, ("id", "btn"))

    def test_click(self):
        with patch.object(self.elem, "_find", return_value=self.e):
            self.elem.click()
        self.e.click.assert_called_once()

    def test_send_keys(self):
        with patch.object(self.elem, "_find", return_value=self.e):
            self.elem.send_keys("hello")
        self.e.send_keys.assert_called_once_with("hello")

    def test_clear(self):
        with patch.object(self.elem, "_find", return_value=self.e):
            self.elem.clear()
        self.e.clear.assert_called_once()

    def test_clear_and_type(self):
        with patch.object(self.elem, "_find", return_value=self.e):
            self.elem.clear_and_type("text")
        self.e.clear.assert_called_once()
        self.e.send_keys.assert_called_once_with("text")

    def test_text_property(self):
        with patch.object(self.elem, "_find", return_value=self.e):
            self.e.text = "hello"
            assert self.elem.text == "hello"

    def test_is_displayed_true(self):
        with patch.object(self.elem, "_find", return_value=self.e):
            self.e.is_displayed.return_value = True
            assert self.elem.is_displayed is True

    def test_is_displayed_false_on_exception(self):
        with patch.object(self.elem, "_find", side_effect=Exception()):
            assert self.elem.is_displayed is False

    def test_is_enabled(self):
        with patch.object(self.elem, "_find", return_value=self.e):
            self.e.is_enabled.return_value = True
            assert self.elem.is_enabled is True

    def test_is_enabled_false_on_exception(self):
        with patch.object(self.elem, "_find", side_effect=Exception("error")):
            assert self.elem.is_enabled is False

    def test_get_attribute(self):
        with patch.object(self.elem, "_find", return_value=self.e):
            self.e.get_attribute.return_value = "val"
            assert self.elem.get_attribute("resource-id") == "val"

    def test_retry_on_stale(self):
        fresh = MagicMock()
        calls = [0]

        def find():
            calls[0] += 1
            if calls[0] == 1:
                raise StaleElementReferenceException()
            return fresh

        with patch.object(self.elem, "_find", side_effect=find):
            self.elem.click()

        assert calls[0] == 2
        fresh.click.assert_called_once()

    def test_raises_after_3_stale(self):
        with patch.object(self.elem, "_find", side_effect=StaleElementReferenceException()):
            with pytest.raises(StaleElementReferenceException):
                self.elem._safe_action("click")

    def test_find_calls_webdriverwait(self):
        mock_result = MagicMock()
        with patch("mobius.elements.mobile_element.WebDriverWait") as W:
            W.return_value.until.return_value = mock_result
            result = self.elem._find()
        assert result == mock_result

    def test_repr(self):
        e = MobileElement(MagicMock(), ("accessibility id", "Login"))
        assert "Login" in repr(e)


@pytest.mark.unit
class TestMobileElementStaleRetry:
    """Покрываем retry loop в text property — StaleElement на первой попытке."""

    def test_text_retries_on_stale_element(self):
        from selenium.common.exceptions import StaleElementReferenceException

        d = MagicMock()
        elem = MobileElement(d, ("id", "label"))
        calls = [0]
        real_elem = MagicMock()
        real_elem.text = "Hello"

        def find_side_effect():
            calls[0] += 1
            if calls[0] == 1:
                raise StaleElementReferenceException()
            return real_elem

        with patch.object(elem, "_find", side_effect=find_side_effect):
            result = elem.text

        assert result == "Hello"
        assert calls[0] == 2

    def test_text_raises_after_max_retries(self):
        from selenium.common.exceptions import StaleElementReferenceException

        d = MagicMock()
        elem = MobileElement(d, ("id", "label"))
        with patch.object(elem, "_find", side_effect=StaleElementReferenceException()):
            with pytest.raises(StaleElementReferenceException):
                _ = elem.text
