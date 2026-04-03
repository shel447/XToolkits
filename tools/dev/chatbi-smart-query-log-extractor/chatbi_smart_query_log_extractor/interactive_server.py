from __future__ import annotations

import json
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

import requests


class ReportServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        report: dict[str, Any],
        html_content: str,
    ) -> None:
        super().__init__(server_address, ReportRequestHandler)
        self.report = report
        self.html_content = html_content
        host, port = self.server_address
        display_host = "127.0.0.1" if host in {"0.0.0.0", ""} else host
        self.base_url = f"http://{display_host}:{port}"


class ReportRequestHandler(BaseHTTPRequestHandler):
    server: ReportServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._send_html(self.server.html_content)
            return
        if parsed.path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/execute-prompt":
            self._handle_execute_prompt()
            return
        if parsed.path == "/chat/completion":
            self._handle_fake_chat_completion()
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _handle_execute_prompt(self) -> None:
        payload = self._read_json_body()
        if payload is None:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid json body"})
            return

        request_id = str(payload.get("request_id", "")).strip()
        if not request_id:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "request_id is required"})
            return

        messages = _find_prompt_messages(self.server.report, request_id)
        if messages is None:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "prompt messages not found"})
            return

        try:
            response = requests.post(
                f"{self.server.base_url}/chat/completion",
                json={"model": "fake-chat-completion", "messages": messages},
                timeout=30,
                verify=False,
            )
            response.raise_for_status()
            self._send_json(HTTPStatus.OK, response.json())
        except requests.RequestException as exc:
            self._send_json(HTTPStatus.BAD_GATEWAY, {"error": f"upstream request failed: {exc}"})

    def _handle_fake_chat_completion(self) -> None:
        payload = self._read_json_body()
        if payload is None:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid json body"})
            return

        messages = payload.get("messages")
        if not isinstance(messages, list) or len(messages) < 2:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "messages field missing or incomplete"})
            return

        system = _extract_message_content(messages, 0)
        user = _extract_message_content(messages, 1)
        content = f"FAKE RESPONSE\n\nSYSTEM:\n{system}\n\nUSER:\n{user}"
        response = {
            "id": f"fake-chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": payload.get("model", "fake-chat-completion"),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
        }
        self._send_json(HTTPStatus.OK, response)

    def _read_json_body(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_report_server(
    report: dict[str, Any],
    html_content: str,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> ReportServer:
    return ReportServer((host, port), report=report, html_content=html_content)


def serve_report(
    report: dict[str, Any],
    html_content: str,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> None:
    server = build_report_server(report, html_content, host=host, port=port)
    try:
        print(f"Interactive report server started: {server.base_url}")
        server.serve_forever()
    finally:
        server.server_close()


def _find_prompt_messages(report: dict[str, Any], request_id: str) -> list[dict[str, str]] | None:
    for question_group in report.get("questions", []):
        for match in question_group.get("matches", []):
            if match.get("request_id") != request_id:
                continue
            prompt = match.get("final_prompt", {})
            system = prompt.get("system", "")
            user = prompt.get("user", "")
            if not system or not user:
                return None
            return [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
    return None


def _extract_message_content(messages: list[Any], index: int) -> str:
    if index >= len(messages):
        return ""
    message = messages[index]
    if not isinstance(message, dict):
        return ""
    content = message.get("content", "")
    return content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
