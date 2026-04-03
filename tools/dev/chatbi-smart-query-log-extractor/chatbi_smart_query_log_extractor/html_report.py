from __future__ import annotations

from html import escape
from typing import Any


def render_html(report: dict[str, Any]) -> str:
    question = escape(report["question"])
    source_log = escape(report["source_log"])
    generated_at = escape(report["generated_at"])
    total_matches = report["total_matches"]

    nav_items = []
    detail_sections = []
    for match in report["matches"]:
        anchor_id = f"match-{match['index']}"
        nav_label = f"{match['anchor_timestamp']} | {match['request_id']}"
        nav_items.append(f'<li><a href="#{anchor_id}">{escape(nav_label)}</a></li>')
        detail_sections.append(_render_match(anchor_id, match))

    nav_html = "".join(nav_items) if nav_items else "<li>未匹配到任何调用</li>"
    details_html = "".join(detail_sections) if detail_sections else "<section class=\"empty\">未匹配到任何调用。</section>"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>ChatBI 智能问数关键日志提取结果</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f7fb;
      --surface: #ffffff;
      --border: #d7deea;
      --text: #1d2738;
      --muted: #66758c;
      --accent: #0f766e;
      --warn-bg: #fff6db;
      --warn-border: #f1c24b;
    }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: linear-gradient(180deg, #eef4ff 0%, var(--bg) 220px);
      color: var(--text);
    }}
    .page {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 24px;
    }}
    .summary, .match, .empty {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 16px;
      box-shadow: 0 8px 30px rgba(15, 23, 42, 0.06);
    }}
    .summary {{
      padding: 24px;
      margin-bottom: 24px;
    }}
    .layout {{
      display: grid;
      grid-template-columns: 280px 1fr;
      gap: 20px;
      align-items: start;
    }}
    .nav {{
      position: sticky;
      top: 16px;
      background: rgba(255, 255, 255, 0.9);
      backdrop-filter: blur(8px);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 18px;
    }}
    .nav ul {{
      margin: 12px 0 0;
      padding-left: 18px;
    }}
    .nav a {{
      color: var(--accent);
      text-decoration: none;
    }}
    .matches {{
      display: grid;
      gap: 20px;
    }}
    .match {{
      padding: 22px;
    }}
    .match h2, .summary h1 {{
      margin: 0 0 12px;
    }}
    .meta {{
      color: var(--muted);
      font-size: 14px;
      margin-bottom: 16px;
    }}
    .section {{
      margin-top: 18px;
    }}
    .section h3 {{
      margin: 0 0 8px;
      font-size: 16px;
    }}
    pre {{
      margin: 0;
      padding: 14px;
      background: #0f172a;
      color: #e2e8f0;
      border-radius: 12px;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .list {{
      margin: 0;
      padding-left: 20px;
    }}
    .missing, .errors {{
      padding: 12px 14px;
      border-radius: 12px;
      border: 1px solid var(--warn-border);
      background: var(--warn-bg);
    }}
    .empty {{
      padding: 24px;
    }}
    @media (max-width: 960px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}
      .nav {{
        position: static;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="summary">
      <h1>ChatBI 智能问数关键日志提取结果</h1>
      <div class="meta">问题：{question}</div>
      <div class="meta">日志文件：{source_log}</div>
      <div class="meta">命中调用数：{total_matches}</div>
      <div class="meta">生成时间：{generated_at}</div>
    </section>
    <div class="layout">
      <aside class="nav">
        <strong>调用导航</strong>
        <ul>{nav_html}</ul>
      </aside>
      <main class="matches">{details_html}</main>
    </div>
  </div>
</body>
</html>"""


def _render_match(anchor_id: str, match: dict[str, Any]) -> str:
    title = f"{match['anchor_timestamp']} | {match['request_id']} | 第 {match['index']} 次调用"
    sections = [
        _render_text_section("命中锚点日志", match["anchor_line"]),
        _render_list_section("RAG 检索结果", match["rag_results"]),
        _render_text_section("问题改写", match["rewritten_question"]),
        _render_list_section("表检索结果", match["recalled_tables"]),
        _render_text_section("IR 表定义", match["ir_table_definition"]),
        _render_prompt_section(match["final_prompt"]),
        _render_text_section("生成 IR 结果", match["generated_ir"]),
    ]

    if match["missing_sections"]:
        sections.append(
            _render_list_section(
                "缺失字段",
                [f"{field}: 未命中该字段" for field in match["missing_sections"]],
                kind="missing",
            )
        )
    if match["parse_errors"]:
        sections.append(_render_list_section("解析错误", match["parse_errors"], kind="errors"))

    return f"""
    <section id="{escape(anchor_id)}" class="match">
      <h2>{escape(title)}</h2>
      <div class="meta">调用 ID：{escape(match['request_id'])}</div>
      {''.join(sections)}
    </section>
    """


def _render_text_section(title: str, content: str) -> str:
    if not content:
        return f"""
        <section class="section">
          <h3>{escape(title)}</h3>
          <div class="missing">未命中该字段</div>
        </section>
        """
    return f"""
    <section class="section">
      <h3>{escape(title)}</h3>
      <pre>{escape(content)}</pre>
    </section>
    """


def _render_list_section(title: str, items: list[str], kind: str | None = None) -> str:
    if not items:
        return f"""
        <section class="section">
          <h3>{escape(title)}</h3>
          <div class="missing">未命中该字段</div>
        </section>
        """
    class_name = kind or "list"
    rendered_items = "".join(f"<li>{escape(item)}</li>" for item in items)
    return f"""
    <section class="section">
      <h3>{escape(title)}</h3>
      <ul class="{escape(class_name)}">{rendered_items}</ul>
    </section>
    """


def _render_prompt_section(prompt: dict[str, str]) -> str:
    if not any(prompt.values()):
        return """
        <section class="section">
          <h3>最终 Prompt</h3>
          <div class="missing">未命中该字段</div>
        </section>
        """

    blocks = []
    if prompt.get("system"):
        blocks.append(_render_text_section("Prompt / system", prompt["system"]))
    if prompt.get("user"):
        blocks.append(_render_text_section("Prompt / user", prompt["user"]))
    if prompt.get("combined"):
        blocks.append(_render_text_section("Prompt / combined", prompt["combined"]))
    if prompt.get("raw") and not prompt.get("combined"):
        blocks.append(_render_text_section("Prompt / raw", prompt["raw"]))
    return f"""
    <section class="section">
      <h3>最终 Prompt</h3>
      {''.join(blocks)}
    </section>
    """
