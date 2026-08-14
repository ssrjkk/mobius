"""
Минимальный HTTP-сервер, эмулирующий W3C WebDriver protocol — ровно
настолько, чтобы Appium-Python-Client мог создать реальную сессию и
отправить реальные команды по проводу.

Это НЕ замена реальному Appium — сервер ничего не знает про Android/iOS,
просто отвечает правдоподобным JSON на любой WebDriver-запрос и запоминает
всё что получил. Цель: доказать что framework отправляет корректные HTTP
запросы (правильный JSON envelope, правильные пути, правильные capabilities)
через настоящий транспортный слой Appium-Python-Client/urllib3 — не через
MagicMock, который проходит вне зависимости от того, что реально было бы
отправлено реальному Appium серверу.

Использование:
    with FakeWebDriverServer() as server:
        driver = create_driver(caps, server_url=server.url)
        driver.find_element(...)
        assert server.last_request("POST", "/session/*/element") is not None
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


@dataclass
class RecordedRequest:
    method: str
    path: str
    body: dict[str, Any] | None


class FakeWebDriverServer:
    """
    Локальный HTTP сервер на случайном порту, реализующий достаточно
    W3C WebDriver protocol чтобы Appium-Python-Client создал сессию
    и отправил команды не падая на транспортном уровне.
    """

    def __init__(self) -> None:
        self._requests: list[RecordedRequest] = []
        self._lock = threading.Lock()
        self._session_id = f"fake-session-{uuid.uuid4().hex[:8]}"
        self._element_counter = 0
        server_self = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                pass  # тишина в stdout тестов

            def _read_body(self) -> dict[str, Any] | None:
                length = int(self.headers.get("Content-Length", 0))
                if length == 0:
                    return None
                raw = self.rfile.read(length)
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return None

            def _respond_json(self, status: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _record(self, method: str, path: str, body: dict[str, Any] | None) -> None:
                with server_self._lock:
                    server_self._requests.append(RecordedRequest(method, path, body))

            def do_GET(self) -> None:
                self._record("GET", self.path, None)
                if self.path == "/status":
                    self._respond_json(200, {"value": {"ready": True, "message": "fake"}})
                elif "/orientation" in self.path:
                    self._respond_json(200, {"value": "PORTRAIT"})
                elif "/screenshot" in self.path:
                    self._respond_json(200, {"value": "ZmFrZV9wbmc="})
                elif "/text" in self.path:
                    self._respond_json(200, {"value": "fake element text"})
                elif "/source" in self.path:
                    self._respond_json(200, {"value": "<hierarchy/>"})
                else:
                    self._respond_json(200, {"value": None})

            def do_POST(self) -> None:
                body = self._read_body()
                self._record("POST", self.path, body)

                if self.path == "/session":
                    caps = {}
                    if body:
                        caps = body.get("capabilities", {}).get("alwaysMatch", {}) or body.get(
                            "desiredCapabilities", {}
                        )
                    self._respond_json(
                        200,
                        {
                            "value": {
                                "sessionId": server_self._session_id,
                                "capabilities": caps,
                            }
                        },
                    )
                elif self.path.endswith("/element"):
                    server_self._element_counter += 1
                    elem_id = f"elem-{server_self._element_counter}"
                    self._respond_json(
                        200, {"value": {"element-6066-11e4-a52e-4f735466cecf": elem_id}}
                    )
                elif "/elements" in self.path:
                    self._respond_json(
                        200, {"value": [{"element-6066-11e4-a52e-4f735466cecf": "elem-1"}]}
                    )
                else:
                    # click, send_keys, actions, execute/sync (mobile: commands), и т.д.
                    self._respond_json(200, {"value": None})

            def do_DELETE(self) -> None:
                self._record("DELETE", self.path, None)
                self._respond_json(200, {"value": None})

        self._handler_cls = Handler
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> FakeWebDriverServer:
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler_cls)
        port = self._httpd.server_address[1]
        self.url = f"http://127.0.0.1:{port}"
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()

    def requests_matching(self, method: str, path_substring: str) -> list[RecordedRequest]:
        with self._lock:
            return [r for r in self._requests if r.method == method and path_substring in r.path]

    def last_request(self, method: str, path_substring: str) -> RecordedRequest | None:
        matches = self.requests_matching(method, path_substring)
        return matches[-1] if matches else None

    @property
    def all_requests(self) -> list[RecordedRequest]:
        with self._lock:
            return list(self._requests)
