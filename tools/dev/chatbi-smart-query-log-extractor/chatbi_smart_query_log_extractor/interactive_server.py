from __future__ import annotations

import base64
import json
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from .extractor import decode_log_bytes, extract_report
from .html_report import render_html
from .ir_executor import ExecutorConfigError, IRExecutionRequestError, execute_complete_ir


class ReportServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        report: dict[str, Any] | None,
        html_content: str | None,
        config_path: str | Path | None = None,
    ) -> None:
        super().__init__(server_address, ReportRequestHandler)
        self.report = report
        self.html_content = html_content or ""
        self.config_path = Path(config_path).resolve() if config_path is not None else None
        host, port = self.server_address
        display_host = "127.0.0.1" if host in {"0.0.0.0", ""} else host
        self.base_url = f"http://{display_host}:{port}"


class ReportRequestHandler(BaseHTTPRequestHandler):
    server: ReportServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._send_html(_render_service_page(self.server.report is not None))
            return
        if parsed.path == "/report/current":
            self._send_html(self.server.html_content or _render_empty_report_page())
            return
        if parsed.path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/report":
            self._handle_parse_report()
            return
        if parsed.path == "/api/execute-prompt":
            self._handle_execute_prompt()
            return
        if parsed.path == "/api/execute-ir":
            self._handle_execute_ir()
            return
        if parsed.path == "/chat/completion":
            self._handle_fake_chat_completion()
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _handle_execute_prompt(self) -> None:
        if self.server.report is None:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "no report loaded"})
            return
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

    def _handle_parse_report(self) -> None:
        payload = self._read_json_body()
        if payload is None:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid json body"})
            return

        source_name = payload.get("source_name")
        if not isinstance(source_name, str) or not source_name.strip():
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "source_name is required"})
            return

        content_base64 = payload.get("content_base64")
        if not isinstance(content_base64, str) or not content_base64.strip():
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "content_base64 is required"})
            return

        encoding = payload.get("encoding")
        if encoding is not None and not isinstance(encoding, str):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "encoding must be a string"})
            return

        try:
            raw = base64.b64decode(content_base64.encode("ascii"), validate=True)
            log_text = decode_log_bytes(raw, encoding=encoding)
        except (ValueError, UnicodeDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"failed to decode uploaded log: {exc}"})
            return

        report = extract_report(log_text, source_name.strip())
        self.server.report = report
        self.server.html_content = render_html(report)
        total_matches = sum(question_group["total_matches"] for question_group in report["questions"])
        self._send_json(
            HTTPStatus.OK,
            {
                "source_log": report["source_log"],
                "total_questions": report["total_questions"],
                "total_matches": total_matches,
                "report_url": "/report/current",
            },
        )

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

    def _handle_execute_ir(self) -> None:
        if self.server.report is None:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "no report loaded"})
            return
        payload = self._read_json_body()
        if payload is None:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid json body"})
            return

        request_id = str(payload.get("request_id", "")).strip()
        if not request_id:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "request_id is required"})
            return

        executor_name = payload.get("executor")
        if executor_name is not None and not isinstance(executor_name, str):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "executor must be a string"})
            return

        source_filename = payload.get("source_filename")
        if source_filename is not None and not isinstance(source_filename, str):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "source_filename must be a string"})
            return

        try:
            result = execute_complete_ir(
                self.server.report,
                request_id=request_id,
                executor_name=executor_name,
                source_filename=source_filename,
                config_path=self.server.config_path,
            )
        except IRExecutionRequestError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        except ExecutorConfigError as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return

        self._send_json(HTTPStatus.OK, result)

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
    report: dict[str, Any] | None,
    html_content: str | None,
    host: str = "127.0.0.1",
    port: int = 8000,
    config_path: str | Path | None = None,
) -> ReportServer:
    return ReportServer((host, port), report=report, html_content=html_content, config_path=config_path)


def serve_report(
    report: dict[str, Any] | None,
    html_content: str | None,
    host: str = "127.0.0.1",
    port: int = 8000,
    config_path: str | Path | None = None,
) -> None:
    server = build_report_server(report, html_content, host=host, port=port, config_path=config_path)
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


def _render_service_page(has_report: bool) -> str:
    initial_src = "/report/current" if has_report else "about:blank"
    initial_status = "已加载初始报告" if has_report else "请选择一个日志文件，或先选择日志目录再点文件名。"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>ChatBI 日志浏览服务</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f7fb;
      --panel: #ffffff;
      --border: #d7deea;
      --text: #1d2738;
      --muted: #66758c;
      --accent: #0f766e;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: linear-gradient(180deg, #eef4ff 0%, var(--bg) 260px);
      color: var(--text);
    }}
    .page {{
      max-width: 1600px;
      margin: 0 auto;
      padding: 24px;
      display: grid;
      gap: 20px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 16px;
      box-shadow: 0 8px 30px rgba(15, 23, 42, 0.06);
      padding: 20px;
    }}
    .controls {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      margin-top: 12px;
    }}
    .picker-label {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 120px;
      height: 38px;
      padding: 0 14px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: #f8fbff;
      color: var(--accent);
      cursor: pointer;
      font-size: 14px;
      font-weight: 600;
    }}
    .picker-label:hover {{
      background: #e8f5f2;
    }}
    .picker-input {{
      display: none;
    }}
    .layout {{
      display: grid;
      grid-template-columns: 320px 1fr;
      gap: 20px;
      align-items: start;
    }}
    .file-list {{
      display: grid;
      gap: 10px;
      max-height: 70vh;
      overflow: auto;
    }}
    .file-item {{
      width: 100%;
      text-align: left;
      padding: 10px 12px;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: #ffffff;
      color: var(--text);
      cursor: pointer;
    }}
    .file-item:hover {{
      border-color: #9cc9c4;
      background: #f7fcfb;
    }}
    .file-item.active {{
      border-color: #0f766e;
      background: #edf9f7;
    }}
    .status {{
      margin-top: 12px;
      font-size: 13px;
      color: var(--muted);
      white-space: pre-wrap;
    }}
    .report-frame {{
      width: 100%;
      min-height: 78vh;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: #ffffff;
    }}
    @media (max-width: 1080px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}
      .report-frame {{
        min-height: 60vh;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="panel">
      <h1>ChatBI 日志浏览服务</h1>
      <div>固定单端口运行。你可以直接在这个页面选择日志文件，或选择日志目录后按文件逐个解析。</div>
      <div class="controls">
        <label class="picker-label" for="log-file-input">选择日志文件</label>
        <input id="log-file-input" class="picker-input" type="file" accept=".log,.txt,.out,.text,*/*" />
        <label class="picker-label" for="log-directory-input">选择日志目录</label>
        <input id="log-directory-input" class="picker-input" type="file" webkitdirectory directory multiple />
      </div>
      <div id="service-status" class="status">{initial_status}</div>
    </section>
    <div class="layout">
      <section class="panel">
        <h2>已选日志文件</h2>
        <div id="selected-files" class="file-list">
          <div class="status">暂无文件</div>
        </div>
      </section>
      <section class="panel">
        <h2>解析结果</h2>
        <iframe id="report-frame" class="report-frame" src="{initial_src}" title="解析结果"></iframe>
      </section>
    </div>
  </div>
  <script>
    let selectedFiles = [];
    let activeFileIndex = -1;

    function setStatus(text) {{
      const status = document.getElementById('service-status');
      if (status) {{
        status.textContent = text;
      }}
    }}

    function renderSelectedFiles() {{
      const container = document.getElementById('selected-files');
      if (!container) {{
        return;
      }}
      if (!selectedFiles.length) {{
        container.innerHTML = '<div class="status">暂无文件</div>';
        return;
      }}
      container.innerHTML = selectedFiles.map((file, index) => {{
        const label = escapeHtml(file.relativeLabel || file.name);
        const activeClass = index === activeFileIndex ? ' active' : '';
        return `<button type="button" class="file-item${{activeClass}}" data-index="${{index}}">${{label}}</button>`;
      }}).join('');
      container.querySelectorAll('.file-item').forEach((button) => {{
        button.addEventListener('click', () => parseSelectedFile(Number(button.getAttribute('data-index'))));
      }});
    }}

    function escapeHtml(text) {{
      return text
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }}

    function handleSelectedFiles(fileList) {{
      selectedFiles = Array.from(fileList || []).map((file) => {{
        const relativeLabel = file.webkitRelativePath || file.name;
        return {{ file, name: file.name, relativeLabel }};
      }});
      selectedFiles.sort((left, right) => left.relativeLabel.localeCompare(right.relativeLabel, 'zh-CN'));
      activeFileIndex = -1;
      renderSelectedFiles();
      if (selectedFiles.length) {{
        parseSelectedFile(0);
      }} else {{
        setStatus('没有选到任何文件。');
      }}
    }}

    async function parseSelectedFile(index) {{
      if (index < 0 || index >= selectedFiles.length) {{
        return;
      }}
      activeFileIndex = index;
      renderSelectedFiles();
      const fileEntry = selectedFiles[index];
      setStatus(`正在解析: ${{fileEntry.relativeLabel}}`);
      try {{
        const buffer = await fileEntry.file.arrayBuffer();
        const bytes = new Uint8Array(buffer);
        let binary = '';
        for (let offset = 0; offset < bytes.length; offset += 0x8000) {{
          const chunk = bytes.subarray(offset, offset + 0x8000);
          binary += String.fromCharCode(...chunk);
        }}
        const contentBase64 = btoa(binary);
        const response = await fetch('/api/report', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            source_name: fileEntry.relativeLabel,
            content_base64: contentBase64,
          }}),
        }});
        const payload = await response.json();
        if (!response.ok) {{
          throw new Error(payload.error || `HTTP ${{response.status}}`);
        }}
        const frame = document.getElementById('report-frame');
        if (frame) {{
          frame.src = `${{payload.report_url}}?ts=${{Date.now()}}`;
        }}
        setStatus(`已解析: ${{payload.source_log}}\\n问题数: ${{payload.total_questions}}\\n调用数: ${{payload.total_matches}}`);
      }} catch (error) {{
        setStatus(`解析失败: ${{error.message}}`);
      }}
    }}

    document.getElementById('log-file-input')?.addEventListener('change', (event) => {{
      handleSelectedFiles(event.target.files);
    }});

    document.getElementById('log-directory-input')?.addEventListener('change', (event) => {{
      handleSelectedFiles(event.target.files);
    }});
  </script>
</body>
</html>"""


def _render_empty_report_page() -> str:
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>未加载日志</title>
  <style>
    body {
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: #f5f7fb;
      color: #1d2738;
      display: grid;
      place-items: center;
      min-height: 100vh;
    }
    .empty {
      padding: 28px 32px;
      background: #ffffff;
      border: 1px solid #d7deea;
      border-radius: 16px;
      box-shadow: 0 8px 30px rgba(15, 23, 42, 0.06);
    }
  </style>
</head>
<body>
  <section class="empty">未加载日志。请返回上一个页面选择日志文件或日志目录。</section>
</body>
</html>"""
