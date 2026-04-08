from __future__ import annotations

import json
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
            match_nav_items.append(f"<li>{_render_nav_match_link(anchor_id, match)}</li>")
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
      --success-bg: #dff6f0;
      --success-fg: #0f766e;
      --danger-bg: #fff0f0;
      --danger-border: #ef9a9a;
      --danger-fg: #b42318;
    }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: linear-gradient(180deg, #eef4ff 0%, var(--bg) 220px);
      color: var(--text);
    }}
    .page {{
      width: 100%;
      margin: 0;
      padding: 10px 12px 14px;
      box-sizing: border-box;
    }}
    .summary, .match, .empty {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 16px;
      box-shadow: 0 8px 30px rgba(15, 23, 42, 0.06);
    }}
    .summary {{
      padding: 14px 16px;
      margin-bottom: 14px;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 8px 14px;
    }}
    .layout {{
      display: grid;
      grid-template-columns: 280px 1fr;
      gap: 14px;
      align-items: start;
    }}
    .nav {{
      position: sticky;
      top: 12px;
      max-height: calc(100vh - 24px);
      overflow-y: auto;
      background: rgba(255, 255, 255, 0.9);
      backdrop-filter: blur(8px);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 14px;
    }}
    .nav ul {{
      margin: 10px 0 0;
      padding-left: 18px;
    }}
    .nav a {{
      color: var(--accent);
      text-decoration: none;
    }}
    .nav > ul > li > a {{
      display: block;
      padding: 6px 10px;
      border: 1px solid transparent;
      border-radius: 10px;
      transition: background 0.16s ease, border-color 0.16s ease, color 0.16s ease;
    }}
    .nav a.nav-active {{
      background: #e8f5f2;
      border-color: #9ad8cb;
      color: var(--accent);
      font-weight: 700;
    }}
    .nav a.nav-parent-active {{
      background: #eef6ff;
      border-color: #c8daf6;
      color: #24548f;
    }}
    .nav-match-link {{
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 6px 10px;
      border: 1px solid transparent;
      border-radius: 10px;
      transition: background 0.16s ease, border-color 0.16s ease, color 0.16s ease;
    }}
    .nav-status {{
      position: relative;
      width: 22px;
      height: 22px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 999px;
      font-size: 14px;
      font-weight: 700;
      flex: 0 0 auto;
    }}
    .nav-status-success {{
      color: var(--success-fg);
      background: var(--success-bg);
    }}
    .nav-status-failed {{
      color: var(--danger-fg);
      background: #ffe3e3;
    }}
    .nav-status-unknown {{
      color: #66758c;
      background: #edf1f7;
    }}
    .nav-retry-badge {{
      position: absolute;
      top: -6px;
      right: -8px;
      min-width: 16px;
      height: 16px;
      padding: 0 4px;
      border-radius: 999px;
      border: 1px solid currentColor;
      background: #ffffff;
      font-size: 10px;
      line-height: 14px;
      text-align: center;
      box-sizing: border-box;
    }}
    .nav-match-time {{
      color: var(--text);
    }}
    .matches {{
      display: grid;
      gap: 14px;
    }}
    .question-group {{
      display: grid;
      gap: 16px;
      padding: 18px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 16px;
      box-shadow: 0 8px 30px rgba(15, 23, 42, 0.06);
    }}
    .match {{
      padding: 18px;
    }}
    .match h2, .summary h1, .question-group h2 {{
      margin: 0 0 10px;
    }}
    .meta {{
      color: var(--muted);
      font-size: 14px;
      margin-bottom: 0;
    }}
    .section {{
      margin-top: 18px;
    }}
    .section h3 {{
      margin: 0 0 8px;
      font-size: 16px;
    }}
    .status-summary {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 16px;
    }}
    .status-chip {{
      display: inline-flex;
      align-items: center;
      min-height: 32px;
      padding: 0 12px;
      border-radius: 999px;
      font-size: 13px;
      font-weight: 600;
      border: 1px solid var(--border);
      background: #f8fbff;
    }}
    .status-chip-success {{
      color: var(--success-fg);
      background: var(--success-bg);
      border-color: #9ad8cb;
    }}
    .status-chip-failed {{
      color: var(--danger-fg);
      background: #ffe3e3;
      border-color: #efb0b0;
    }}
    .status-chip-unknown {{
      color: #516074;
      background: #edf1f7;
      border-color: #cbd5e1;
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
    .section-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 8px;
    }}
    .section-header h3 {{
      margin: 0;
      font-size: 16px;
    }}
    .copy-actions {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }}
    .filename-input {{
      width: 180px;
      height: 28px;
      padding: 0 10px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #ffffff;
      color: var(--text);
      font-size: 12px;
      line-height: 28px;
    }}
    .filename-input::placeholder {{
      color: #8a97aa;
    }}
    .copy-btn {{
      width: 28px;
      height: 28px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #f8fbff;
      color: var(--accent);
      cursor: pointer;
      font-size: 14px;
      line-height: 1;
    }}
    .copy-btn:hover {{
      background: #e8f5f2;
    }}
    .copy-json-btn {{
      width: auto;
      min-width: 42px;
      padding: 0 8px;
      font-size: 11px;
      font-weight: 600;
    }}
    .execute-btn {{
      width: 28px;
      height: 28px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #f8fbff;
      color: var(--accent);
      cursor: pointer;
      font-size: 13px;
      line-height: 1;
    }}
    .execute-btn:hover {{
      background: #e8f5f2;
    }}
    .copy-feedback {{
      min-width: 36px;
      font-size: 12px;
      color: var(--accent);
      opacity: 0;
      transform: translateY(-2px);
      transition: opacity 0.16s ease, transform 0.16s ease;
      pointer-events: none;
    }}
    .copy-feedback.visible {{
      opacity: 1;
      transform: translateY(0);
    }}
    .execute-feedback {{
      min-width: 36px;
      font-size: 12px;
      color: var(--accent);
      opacity: 0;
      transform: translateY(-2px);
      transition: opacity 0.16s ease, transform 0.16s ease;
      pointer-events: none;
    }}
    .execute-feedback.visible {{
      opacity: 1;
      transform: translateY(0);
    }}
    .execute-output {{
      margin-top: 12px;
      border: 1px solid #cfe5d7;
      background: #f5fbf7;
      color: #214236;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
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
    .highlight-block {{
      padding: 12px 14px;
      border-radius: 12px;
      border: 1px solid transparent;
    }}
    .highlight-block .list {{
      margin: 0;
    }}
    .retry-block {{
      background: #fff6db;
      border-color: #f1c24b;
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
        max-height: none;
        overflow-y: visible;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="summary">
      <h1>ChatBI 智能问数关键日志提取结果</h1>
      <div class="summary-grid">
        <div class="meta">日志文件：{source_log}</div>
        <div class="meta">自动发现问题数：{total_questions}</div>
        <div class="meta">命中调用总数：{total_matches}</div>
        <div class="meta">生成时间：{generated_at}</div>
      </div>
    </section>
    <div class="layout">
      <aside class="nav">
        <strong>问题导航</strong>
        <ul>{nav_html}</ul>
      </aside>
      <main class="matches">{details_html}</main>
    </div>
  </div>
  <script>
    async function copySection(button) {{
      const targetId = button.getAttribute('data-copy-target');
      const target = document.getElementById(targetId);
      const feedback = button.parentElement ? button.parentElement.querySelector('.copy-feedback') : null;
      if (!target) {{
        return;
      }}
      const text = target.textContent || target.innerText || '';
      try {{
        if (navigator.clipboard && navigator.clipboard.writeText) {{
          await navigator.clipboard.writeText(text);
        }} else {{
          const temp = document.createElement('textarea');
          temp.value = text;
          document.body.appendChild(temp);
          temp.select();
          document.execCommand('copy');
          document.body.removeChild(temp);
        }}
        button.setAttribute('title', '已复制');
        if (feedback) {{
          feedback.textContent = '已复制';
          feedback.classList.add('visible');
          if (feedback._timer) {{
            clearTimeout(feedback._timer);
          }}
          feedback._timer = setTimeout(() => {{
            feedback.classList.remove('visible');
          }}, 1200);
        }}
      }} catch (error) {{
        button.setAttribute('title', '复制失败');
        if (feedback) {{
          feedback.textContent = '复制失败';
          feedback.classList.add('visible');
          if (feedback._timer) {{
            clearTimeout(feedback._timer);
          }}
          feedback._timer = setTimeout(() => {{
            feedback.classList.remove('visible');
          }}, 1200);
        }}
      }}
    }}

    async function executePrompt(button) {{
      const matchId = button.getAttribute('data-execute-match-id');
      const outputId = button.getAttribute('data-execute-output');
      const output = outputId ? document.getElementById(outputId) : null;
      const feedback = button.parentElement ? button.parentElement.querySelector('.execute-feedback') : null;
      if (!matchId || !output) {{
        return;
      }}
      output.hidden = false;
      output.textContent = '执行中...';
      try {{
        const response = await fetch('/api/execute-prompt', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ match_id: matchId }}),
        }});
        const payload = await response.json();
        if (!response.ok) {{
          throw new Error(payload.error || `HTTP ${{response.status}}`);
        }}
        const content = payload?.choices?.[0]?.message?.content;
        output.textContent = typeof content === 'string' ? content : JSON.stringify(payload, null, 2);
        if (feedback) {{
          feedback.textContent = '已执行';
          feedback.classList.add('visible');
          if (feedback._timer) {{
            clearTimeout(feedback._timer);
          }}
          feedback._timer = setTimeout(() => {{
            feedback.classList.remove('visible');
          }}, 1200);
        }}
      }} catch (error) {{
        output.textContent = `执行失败: ${{error.message}}`;
        if (feedback) {{
          feedback.textContent = '执行失败';
          feedback.classList.add('visible');
          if (feedback._timer) {{
            clearTimeout(feedback._timer);
          }}
          feedback._timer = setTimeout(() => {{
            feedback.classList.remove('visible');
          }}, 1200);
        }}
      }}
    }}

    function setTransientFeedback(feedback, text) {{
      if (!feedback) {{
        return;
      }}
      feedback.textContent = text;
      feedback.classList.add('visible');
      if (feedback._timer) {{
        clearTimeout(feedback._timer);
      }}
      feedback._timer = setTimeout(() => {{
        feedback.classList.remove('visible');
      }}, 1200);
    }}

    function formatExecutionResult(payload) {{
      return [
        payload.success ? '执行成功' : '执行失败',
        `执行器: ${{payload.executor || '-'}}`,
        `目标文件: ${{payload.target_file || '-'}}`,
        `耗时: ${{payload.duration_ms ?? '-'}} ms`,
        '',
        'STDOUT:',
        payload.stdout || '(empty)',
        '',
        'STDERR:',
        payload.stderr || '(empty)',
      ].join('\\n');
    }}

    async function executeIR(button) {{
      const matchId = button.getAttribute('data-execute-match-id');
      const outputId = button.getAttribute('data-execute-output');
      const filenameInputId = button.getAttribute('data-execute-filename-input');
      const output = outputId ? document.getElementById(outputId) : null;
      const filenameInput = filenameInputId ? document.getElementById(filenameInputId) : null;
      const feedback = button.parentElement ? button.parentElement.querySelector('.execute-feedback') : null;
      if (!matchId || !output) {{
        return;
      }}
      output.hidden = false;
      output.textContent = '执行中...';
      try {{
        const response = await fetch('/api/execute-ir', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            match_id: matchId,
            source_filename: filenameInput ? filenameInput.value.trim() : '',
          }}),
        }});
        const payload = await response.json();
        if (!response.ok) {{
          throw new Error(payload.error || `HTTP ${{response.status}}`);
        }}
        output.textContent = formatExecutionResult(payload);
        setTransientFeedback(feedback, payload.success ? '已执行' : '执行失败');
      }} catch (error) {{
        output.textContent = `执行失败: ${{error.message}}`;
        setTransientFeedback(feedback, '执行失败');
      }}
    }}

    function updateActiveNavLinks() {{
      const nav = document.querySelector('.nav');
      if (!nav) {{
        return;
      }}
      const links = Array.from(nav.querySelectorAll('a[href^="#"]'));
      links.forEach((link) => {{
        link.classList.remove('nav-active');
        link.classList.remove('nav-parent-active');
      }});
      const hash = window.location.hash;
      if (!hash) {{
        return;
      }}
      const activeLink = links.find((link) => link.getAttribute('href') === hash);
      if (!activeLink) {{
        return;
      }}
      activeLink.classList.add('nav-active');
      const parentList = activeLink.closest('ul');
      const parentItem = parentList ? parentList.closest('li') : null;
      if (!parentItem) {{
        return;
      }}
      const parentQuestionLink = parentItem.firstElementChild;
      if (parentQuestionLink instanceof HTMLAnchorElement && parentQuestionLink !== activeLink) {{
        parentQuestionLink.classList.add('nav-parent-active');
      }}
    }}

    window.addEventListener('hashchange', updateActiveNavLinks);
    window.addEventListener('DOMContentLoaded', updateActiveNavLinks);
  </script>
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
    title = f"{match['anchor_timestamp']} | 线程 {match['thread_id']} | 第 {match['index']} 次调用"
    associated_threads = match.get("associated_thread_ids", [])
    associated_threads_meta = ""
    if associated_threads:
        associated_threads_meta = f'<div class="meta">关联线程：{escape(", ".join(associated_threads))}</div>'
    sections = [
        _render_status_summary(match),
        _render_highlight_list_section("重试记录", match["verifier_failures"], "retry-block"),
    ]
    sections.extend([
        _render_text_section("命中锚点日志", match["anchor_line"]),
        _render_collapsible_list_section("RAG 检索结果", match["rag_results"]),
        _render_text_section("问题改写", match["rewritten_question"]),
        _render_list_section("表检索结果", match["recalled_tables"]),
        _render_collapsible_text_section("IR 表定义", match["ir_table_definition"]),
        _render_collapsible_prompt_execution_section(
            "最终 Prompt",
            match["final_prompt"].get("combined") or match["final_prompt"].get("raw", ""),
            f"final-prompt-{anchor_id}",
            match_id=match["match_id"],
            executable=bool(match["final_prompt"].get("system") and match["final_prompt"].get("user")),
            prompt=match["final_prompt"],
        ),
        _render_collapsible_text_section("生成 IR 结果", match["generated_ir"]),
        _render_copyable_text_section(
            "完整 IR",
            match["complete_ir"],
            f"complete-ir-{anchor_id}",
            show_execute=True,
            match_id=match["match_id"],
        ),
    ])

    if match["parse_errors"]:
        sections.append(_render_list_section("解析错误", match["parse_errors"], kind="errors"))

    return f"""
    <section id="{escape(anchor_id)}" class="match">
      <h2>{escape(title)}</h2>
      <div class="meta">线程 ID：{escape(match['thread_id'])}</div>
      {associated_threads_meta}
      {''.join(sections)}
    </section>
    """


def _render_nav_match_link(anchor_id: str, match: dict[str, Any]) -> str:
    status = match.get("flow_status", "success")
    if status == "success":
        icon = "✓"
        status_class = "nav-status-success"
    elif status == "failed":
        icon = "✗"
        status_class = "nav-status-failed"
    else:
        icon = "?"
        status_class = "nav-status-unknown"
    return (
        f'<a class="nav-match-link" href="#{escape(anchor_id)}">'
        f'<span class="nav-status {status_class}">'
        f'<span class="nav-status-icon">{icon}</span>'
        f'<span class="nav-retry-badge">{match.get("retry_count", 0)}</span>'
        f"</span>"
        f'<span class="nav-match-time">{escape(match["anchor_timestamp"])}</span>'
        f"</a>"
    )


def _render_status_summary(match: dict[str, Any]) -> str:
    flow_status = match.get("flow_status", "success")
    if flow_status == "success":
        flow_label = "成功"
        status_class = "status-chip-success"
    elif flow_status == "failed":
        flow_label = "失败"
        status_class = "status-chip-failed"
    else:
        flow_label = "未知"
        status_class = "status-chip-unknown"
    return f"""
    <section class="status-summary">
      <span class="status-chip {status_class}">流程状态：{flow_label}</span>
      <span class="status-chip">重试次数：{match.get("retry_count", 0)}</span>
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


def _render_copyable_text_section(
    title: str,
    content: str,
    target_id: str,
    show_execute: bool = False,
    match_id: str | None = None,
) -> str:
    if not content:
        return _render_text_section(title, content)
    execute_button = ""
    if show_execute:
        execute_button = (
            f'<input id="{escape(target_id)}-filename" class="filename-input" type="text" '
            f'placeholder="case_时间戳.py" title="源文件名" />'
            f'<button type="button" class="execute-btn" '
            f'data-execute-match-id="{escape(match_id or "")}" '
            f'data-execute-output="{escape(target_id)}-result" '
            f'data-execute-filename-input="{escape(target_id)}-filename" '
            f'onclick="executeIR(this)" title="执行">▶</button>'
            f'<span class="execute-feedback" aria-live="polite">已执行</span>'
        )
    return f"""
    <section class="section">
      <div class="section-header">
        <h3>{escape(title)}</h3>
        <div class="copy-actions">
          {execute_button}
          <button type="button" class="copy-btn" data-copy-target="{escape(target_id)}" onclick="copySection(this)" title="复制">⧉</button>
          <span class="copy-feedback" aria-live="polite">已复制</span>
        </div>
      </div>
      <pre id="{escape(target_id)}">{escape(content)}</pre>
      <pre id="{escape(target_id)}-result" class="execute-output" hidden></pre>
    </section>
    """


def _render_collapsible_copyable_text_section(title: str, content: str, target_id: str) -> str:
    if not content:
        return _render_text_section(title, content)
    return f"""
    <details class="section collapsible">
      <summary>{escape(title)}</summary>
      <div class="collapsible-body">
        <div class="section-header">
          <div></div>
          <div class="copy-actions">
            <button type="button" class="copy-btn" data-copy-target="{escape(target_id)}" onclick="copySection(this)" title="复制">⧉</button>
            <span class="copy-feedback" aria-live="polite">已复制</span>
          </div>
        </div>
        <pre id="{escape(target_id)}">{escape(content)}</pre>
      </div>
    </details>
    """


def _render_collapsible_prompt_execution_section(
    title: str,
    content: str,
    target_id: str,
    match_id: str,
    executable: bool,
    prompt: dict[str, str] | None = None,
) -> str:
    if not content:
        return _render_text_section(title, content)
    prompt_messages_json = _build_prompt_messages_json(prompt or {})
    json_copy_button = ""
    json_copy_payload = ""
    if prompt_messages_json:
        json_copy_button = (
            f'<button type="button" class="copy-btn copy-json-btn" '
            f'data-copy-target="{escape(target_id)}-messages-json" '
            f'onclick="copySection(this)" title="复制 JSON">JSON</button>'
        )
        json_copy_payload = f'<pre id="{escape(target_id)}-messages-json" hidden>{escape(prompt_messages_json)}</pre>'
    execute_controls = ""
    if executable:
        execute_controls = (
            f'<button type="button" class="execute-btn" '
            f'data-execute-match-id="{escape(match_id)}" '
            f'data-execute-output="{escape(target_id)}-result" '
            f'onclick="executePrompt(this)" title="执行">▶</button>'
            f'<span class="execute-feedback" aria-live="polite">已执行</span>'
        )
    return f"""
    <details class="section collapsible">
      <summary>{escape(title)}</summary>
      <div class="collapsible-body">
        <div class="section-header">
          <div></div>
          <div class="copy-actions">
            {execute_controls}
            {json_copy_button}
            <button type="button" class="copy-btn" data-copy-target="{escape(target_id)}" onclick="copySection(this)" title="复制">⧉</button>
            <span class="copy-feedback" aria-live="polite">已复制</span>
          </div>
        </div>
        <pre id="{escape(target_id)}">{escape(content)}</pre>
        {json_copy_payload}
        <pre id="{escape(target_id)}-result" class="execute-output" hidden></pre>
      </div>
    </details>
    """


def _build_prompt_messages_json(prompt: dict[str, str]) -> str:
    system = prompt.get("system", "")
    user = prompt.get("user", "")
    if not system or not user:
        return ""
    payload = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


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


def _render_highlight_list_section(title: str, items: list[str], block_class: str) -> str:
    if items:
        content = f'<ul class="list">{"".join(f"<li>{escape(item)}</li>" for item in items)}</ul>'
    else:
        content = "未命中该字段"
    return f"""
    <section class="section">
      <h3>{escape(title)}</h3>
      <div class="highlight-block {escape(block_class)}">{content}</div>
    </section>
    """


def _render_collapsible_list_section(title: str, items: list[str], kind: str | None = None) -> str:
    if not items:
        return _render_list_section(title, items, kind)
    class_name = kind or "list"
    rendered_items = "".join(f"<li>{escape(item)}</li>" for item in items)
    return f"""
    <details class="section collapsible">
      <summary>{escape(title)}</summary>
      <div class="collapsible-body">
        <ul class="{escape(class_name)}">{rendered_items}</ul>
      </div>
    </details>
    """
