from __future__ import annotations

from html import escape
from typing import Any


def render_html(report: dict[str, Any]) -> str:
    source_log = escape(report["source_log"])
    generated_at = escape(report["generated_at"])
    total_questions = report["total_questions"]
    total_matches = sum(question_group["total_matches"] for question_group in report["questions"])

    nav_items = []
    detail_sections = []
    for question_index, question_group in enumerate(report["questions"], start=1):
        question_anchor_id = f"question-{question_index}"
        question_label = question_group["question"]
        match_nav_items = []
        for match in question_group["matches"]:
            anchor_id = f"{question_anchor_id}-match-{match['index']}"
            nav_label = f"{match['anchor_timestamp']} | {match['request_id']}"
            match_nav_items.append(f'<li><a href="#{anchor_id}">{escape(nav_label)}</a></li>')
        nested_nav = f"<ul>{''.join(match_nav_items)}</ul>" if match_nav_items else ""
        nav_items.append(
            f'<li><a href="#{question_anchor_id}">{escape(question_label)}</a>{nested_nav}</li>'
        )
        detail_sections.append(_render_question_group(question_anchor_id, question_group))

    nav_html = "".join(nav_items) if nav_items else "<li>未发现任何问题</li>"
    details_html = "".join(detail_sections) if detail_sections else "<section class=\"empty\">未发现任何问题。</section>"

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
    .question-group {{
      display: grid;
      gap: 16px;
      padding: 22px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 16px;
      box-shadow: 0 8px 30px rgba(15, 23, 42, 0.06);
    }}
    .match {{
      padding: 22px;
    }}
    .match h2, .summary h1, .question-group h2 {{
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
    .collapsible {{
      margin-top: 18px;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: #f8fbff;
      padding: 12px 14px;
    }}
    .collapsible > summary {{
      cursor: pointer;
      font-size: 16px;
      font-weight: 600;
      list-style: none;
    }}
    .collapsible > summary::-webkit-details-marker {{
      display: none;
    }}
    .collapsible > summary::before {{
      content: "▸";
      display: inline-block;
      margin-right: 8px;
      color: var(--accent);
      transition: transform 0.15s ease;
    }}
    .collapsible[open] > summary::before {{
      transform: rotate(90deg);
    }}
    .collapsible-body {{
      margin-top: 12px;
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
      <div class="meta">日志文件：{source_log}</div>
      <div class="meta">自动发现问题数：{total_questions}</div>
      <div class="meta">命中调用总数：{total_matches}</div>
      <div class="meta">生成时间：{generated_at}</div>
    </section>
    <div class="layout">
      <aside class="nav">
        <strong>问题导航</strong>
        <ul>{nav_html}</ul>
      </aside>
      <main class="matches">{details_html}</main>
    </div>
  </div>
</body>
</html>"""


def _render_question_group(anchor_id: str, question_group: dict[str, Any]) -> str:
    match_sections = []
    for match in question_group["matches"]:
        match_anchor_id = f"{anchor_id}-match-{match['index']}"
        match_sections.append(_render_match(match_anchor_id, match))
    details_html = "".join(match_sections) if match_sections else '<section class="empty">未匹配到任何调用。</section>'
    return f"""
    <section id="{escape(anchor_id)}" class="question-group">
      <h2>{escape(question_group['question'])}</h2>
      <div class="meta">命中调用数：{question_group['total_matches']}</div>
      {details_html}
    </section>
    """


def _render_match(anchor_id: str, match: dict[str, Any]) -> str:
    title = f"{match['anchor_timestamp']} | {match['request_id']} | 第 {match['index']} 次调用"
    sections = [
        _render_text_section("命中锚点日志", match["anchor_line"]),
        _render_list_section("RAG 检索结果", match["rag_results"]),
        _render_text_section("问题改写", match["rewritten_question"]),
        _render_list_section("表检索结果", match["recalled_tables"]),
        _render_collapsible_text_section("IR 表定义", match["ir_table_definition"]),
        _render_collapsible_prompt_section(match["final_prompt"]),
        _render_collapsible_text_section("生成 IR 结果", match["generated_ir"]),
        _render_text_section("完整 IR", match["complete_ir"]),
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


def _render_collapsible_text_section(title: str, content: str) -> str:
    if not content:
        return _render_text_section(title, content)
    return f"""
    <details class="section collapsible">
      <summary>{escape(title)}</summary>
      <div class="collapsible-body">
        <pre>{escape(content)}</pre>
      </div>
    </details>
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


def _render_collapsible_prompt_section(prompt: dict[str, str]) -> str:
    if not any(prompt.values()):
        return _render_prompt_section(prompt)

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
    <details class="section collapsible">
      <summary>最终 Prompt</summary>
      <div class="collapsible-body">
        {''.join(blocks)}
      </div>
    </details>
    """
