from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .extractor import extract_report, has_partial_failures, read_log_text
from .html_report import render_html
from .interactive_server import serve_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="提取 ChatBI 智能问数关键日志并生成 HTML/JSON 结果。")
    parser.add_argument("--log", help="日志文件路径；未提供时，仅可配合 --serve 启动空白日志浏览服务")
    parser.add_argument("--question", help="可选：只提取该精确问题对应的日志链路；未提供时自动发现全部问题")
    parser.add_argument("--output-dir", default="output", help="输出目录，默认是当前目录下的 output/")
    parser.add_argument("--encoding", help="显式指定日志编码；未指定时自动尝试 UTF-8/GBK")
    parser.add_argument("--json-only", action="store_true", help="仅输出 JSON")
    parser.add_argument("--html-only", action="store_true", help="仅输出 HTML")
    parser.add_argument("--serve", action="store_true", help="生成结果后启动本地交互服务，支持在页面上执行 Prompt")
    parser.add_argument("--host", default="127.0.0.1", help="本地交互服务监听地址，默认 127.0.0.1")
    parser.add_argument("--port", type=int, default=8000, help="本地交互服务监听端口，默认 8000")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    question: str | None = None
    if args.question is not None:
        question = args.question.strip()
        if not question:
            print("question 不能为空", file=sys.stderr)
            return 2

    if args.json_only and args.html_only:
        print("--json-only 与 --html-only 不能同时使用", file=sys.stderr)
        return 2
    if args.port < 0 or args.port > 65535:
        print("--port 必须在 0 到 65535 之间", file=sys.stderr)
        return 2
    if args.log is None and not args.serve:
        print("--log 是必填项，除非使用 --serve 启动空白日志浏览服务", file=sys.stderr)
        return 2

    if args.log is None:
        try:
            serve_report(None, "", host=args.host, port=args.port)
        except KeyboardInterrupt:
            print("\n交互服务已停止", file=sys.stderr)
        return 0

    log_path = Path(args.log)
    if not log_path.is_file():
        print(f"日志文件不存在: {log_path}", file=sys.stderr)
        return 2

    try:
        log_text = read_log_text(log_path, args.encoding)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"读取日志失败: {exc}", file=sys.stderr)
        return 1

    report = extract_report(log_text, str(log_path), question_filter=question)
    html_content = render_html(report)
    output_dir = Path(args.output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_outputs(report, html_content, output_dir, args.json_only, args.html_only)
    except OSError as exc:
        print(f"写出结果失败: {exc}", file=sys.stderr)
        return 1

    exit_code = _resolve_exit_code(report)
    if args.serve:
        try:
            serve_report(report, html_content, host=args.host, port=args.port)
        except KeyboardInterrupt:
            print("\n交互服务已停止", file=sys.stderr)
        return exit_code

    return exit_code


def _resolve_exit_code(report: dict) -> int:
    if report["total_questions"] == 0:
        return 3
    if has_partial_failures(report):
        return 4
    return 0


def _write_outputs(
    report: dict,
    html_content: str,
    output_dir: Path,
    json_only: bool,
    html_only: bool,
) -> None:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_name = f"{timestamp}-chatbi-log-extract"

    if not html_only:
        json_path = output_dir / f"{base_name}.json"
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if not json_only:
        html_path = output_dir / f"{base_name}.html"
        html_path.write_text(html_content, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
