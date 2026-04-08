from __future__ import annotations

from collections import Counter
import json
from html import escape
from typing import Any


def render_html(report: dict[str, Any]) -> str:
    source_log = escape(report["source_log"])
    generated_at = escape(report["generated_at"])
    total_questions = report["total_questions"]
    total_matches = sum(question_group["total_matches"] for question_group in report["questions"])
    summary_stats = _collect_summary_stats(report["questions"])
    summary_metrics_html = _render_summary_metrics(summary_stats)
    summary_retry_reasons_html = _render_summary_retry_reasons(summary_stats["retry_reason_counts"])

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
      --reject-bg: #fff4d6;
      --reject-fg: #9a6700;
      --follow-bg: #e8f2ff;
      --follow-fg: #175cd3;
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
      padding: 0;
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
    .summary-metrics {{
      margin-top: 10px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .summary-chip {{
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 0 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
      border: 1px solid var(--border);
      background: #f8fbff;
      color: #2c3f57;
    }}
    .summary-chip-success {{
      color: var(--success-fg);
      background: var(--success-bg);
      border-color: #9ad8cb;
    }}
    .summary-chip-failed {{
      color: var(--danger-fg);
      background: #ffe3e3;
      border-color: #efb0b0;
    }}
    .summary-chip-unknown {{
      color: #516074;
      background: #edf1f7;
      border-color: #cbd5e1;
    }}
    .summary-chip-retry {{
      color: #7a4a00;
      background: #fff6db;
      border-color: #f1c24b;
    }}
    .summary-chip-reject {{
      color: var(--reject-fg);
      background: var(--reject-bg);
      border-color: #f3c969;
    }}
    .summary-chip-follow-up {{
      color: var(--follow-fg);
      background: var(--follow-bg);
      border-color: #a9c4f6;
    }}
    .summary-reasons {{
      margin-top: 10px;
      padding: 10px 12px;
      border: 1px dashed var(--border);
      border-radius: 12px;
      background: #fafcff;
    }}
    .summary-reasons-title {{
      margin: 0 0 8px;
      font-size: 13px;
      font-weight: 600;
      color: #42546d;
    }}
    .summary-reasons-list {{
      margin: 0;
      padding-left: 18px;
      color: #42546d;
      font-size: 13px;
      line-height: 1.5;
    }}
    .summary-reasons-empty {{
      margin: 0;
      color: #6f7f95;
      font-size: 13px;
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
    .nav-status-reject {{
      color: var(--reject-fg);
      background: var(--reject-bg);
    }}
    .nav-status-follow-up {{
      color: var(--follow-fg);
      background: var(--follow-bg);
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
    .knowledge-group {{
      display: grid;
      gap: 10px;
    }}
    .knowledge-item {{
      padding: 12px 14px;
      border-radius: 12px;
      border: 1px solid var(--border);
      background: #fafcff;
    }}
    .knowledge-item h4 {{
      margin: 0 0 8px;
      font-size: 13px;
      color: #42546d;
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
    .status-chip-reject {{
      color: var(--reject-fg);
      background: var(--reject-bg);
      border-color: #f3c969;
    }}
    .status-chip-follow-up {{
      color: var(--follow-fg);
      background: var(--follow-bg);
      border-color: #a9c4f6;
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
    .knowledge-item pre.knowledge-pre {{
      padding: 10px 12px;
      background: #f3f7fd;
      color: #223247;
      border: 1px solid #d7e0ee;
      border-radius: 8px;
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
      {summary_metrics_html}
      {summary_retry_reasons_html}
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


def _collect_summary_stats(question_groups: list[dict[str, Any]]) -> dict[str, Any]:
    success_count = 0
    failed_count = 0
    unknown_count = 0
    reject_count = 0
    follow_up_count = 0
    failed_retry_count = 0
    retry_reason_counts: Counter[str] = Counter()

    for question_group in question_groups:
        for match in question_group.get("matches", []):
            flow_status = str(match.get("flow_status", "unknown"))
            if flow_status == "success":
                success_count += 1
            elif flow_status == "failed":
                failed_count += 1
            elif flow_status == "reject":
                reject_count += 1
            elif flow_status == "follow_up":
                follow_up_count += 1
            else:
                unknown_count += 1

            verifier_failures = match.get("verifier_failures", [])
            if isinstance(verifier_failures, list):
                for reason in verifier_failures:
                    reason_text = str(reason).strip()
                    if not reason_text:
                        continue
                    failed_retry_count += 1
                    retry_reason_counts[reason_text] += 1

    return {
        "success_count": success_count,
        "failed_count": failed_count,
        "unknown_count": unknown_count,
        "reject_count": reject_count,
        "follow_up_count": follow_up_count,
        "failed_retry_count": failed_retry_count,
        "retry_reason_counts": retry_reason_counts,
    }


def _render_summary_metrics(summary_stats: dict[str, Any]) -> str:
    return f"""
    <section class="summary-metrics">
      <span class="summary-chip summary-chip-success">成功问题数：{summary_stats["success_count"]}</span>
      <span class="summary-chip summary-chip-failed">失败问题数：{summary_stats["failed_count"]}</span>
      <span class="summary-chip summary-chip-unknown">未知问题数：{summary_stats["unknown_count"]}</span>
      <span class="summary-chip summary-chip-reject">拒答问题数：{summary_stats["reject_count"]}</span>
      <span class="summary-chip summary-chip-follow-up">追问问题数：{summary_stats["follow_up_count"]}</span>
      <span class="summary-chip summary-chip-retry">失败重试次数：{summary_stats["failed_retry_count"]}</span>
    </section>
    """


def _render_summary_retry_reasons(retry_reason_counts: Counter[str]) -> str:
    if not retry_reason_counts:
        return """
    <section class="summary-reasons">
      <h3 class="summary-reasons-title">重试原因统计</h3>
      <p class="summary-reasons-empty">无</p>
    </section>
    """

    items = "".join(
        f"<li>{escape(reason)}（{count}次）</li>"
        for reason, count in sorted(retry_reason_counts.items(), key=lambda item: (-item[1], item[0]))
    )
    return f"""
    <section class="summary-reasons">
      <h3 class="summary-reasons-title">重试原因统计</h3>
      <ul class="summary-reasons-list">{items}</ul>
    </section>
    """


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
    skipped_sections = set(match.get("skipped_sections", []))
    preprocess_knowledge = match.get("preprocess_knowledge", {})
    preprocess_group = [
        ("问题改写", _format_knowledge_bundle(preprocess_knowledge.get("rewrite"))),
        ("拒答", "\n".join(str(item).strip() for item in preprocess_knowledge.get("reject", []) if str(item).strip())),
        ("追问", "\n".join(str(item).strip() for item in preprocess_knowledge.get("follow_up", []) if str(item).strip())),
    ]
    sql_knowledge = match.get("sql_knowledge", {})
    sql_generation_knowledge = _format_knowledge_bundle(
        sql_knowledge.get("generation") or match.get("sql_generation_knowledge")
    )
    few_shot_knowledge = _format_knowledge_bundle(
        sql_knowledge.get("few_shot") or match.get("few_shot_knowledge")
    )
    sql_group = [
        ("生成逻辑", sql_generation_knowledge),
        ("Few-shot", few_shot_knowledge),
    ]
    sql_knowledge_skipped = (
        "sql_knowledge" in skipped_sections
        or ("sql_generation_knowledge" in skipped_sections and "few_shot_knowledge" in skipped_sections)
    )
    sections = [
        _render_status_summary(match),
    ]
    sections.extend([
        _render_text_section("命中锚点日志", match["anchor_line"]),
        _render_text_section("AC 补充问题", match.get("ac_enriched_question", "")),
        _render_text_section("预处理改写", match.get("preprocess_rewritten_question", "")),
        _render_grouped_knowledge_section("预处理知识", preprocess_group),
        _render_collapsible_text_section(
            "标准化问题",
            match.get("mask_question", ""),
            skipped="mask_question" in skipped_sections,
        ),
        _render_grouped_knowledge_section("SQL生成知识", sql_group, skipped=sql_knowledge_skipped),
        _render_sql_rewrite_section(
            "问题改写",
            match.get("sql_rewritten_question", "") or match.get("rewritten_question", ""),
            f"sql-rewrite-{anchor_id}",
            match.get("sql_rewrite_prompt_raw", ""),
            match.get("sql_rewrite_prompt_json", ""),
            skipped="sql_rewritten_question" in skipped_sections,
        ),
        _render_list_section(
            "表检索结果",
            match["recalled_tables"],
            skipped="recalled_tables" in skipped_sections,
        ),
        _render_collapsible_text_section(
            "IR 表定义",
            match["ir_table_definition"],
            skipped="ir_table_definition" in skipped_sections,
        ),
        _render_collapsible_prompt_execution_section(
            "最终 Prompt",
            match["final_prompt"].get("combined") or match["final_prompt"].get("raw", ""),
            f"final-prompt-{anchor_id}",
            match_id=match["match_id"],
            executable=bool(match["final_prompt"].get("system") and match["final_prompt"].get("user")),
            prompt=match["final_prompt"],
            skipped="final_prompt" in skipped_sections,
        ),
        _render_highlight_list_section("校验记录", match["verifier_failures"], "retry-block"),
        _render_collapsible_text_section(
            "生成 IR 结果",
            match["generated_ir"],
            skipped="generated_ir" in skipped_sections,
        ),
        _render_copyable_text_section(
            "完整 IR",
            match["complete_ir"],
            f"complete-ir-{anchor_id}",
            show_execute=True,
            match_id=match["match_id"],
            skipped="complete_ir" in skipped_sections,
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
    elif status == "reject":
        icon = "⊘"
        status_class = "nav-status-reject"
    elif status == "follow_up":
        icon = "↺"
        status_class = "nav-status-follow-up"
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
    elif flow_status == "reject":
        flow_label = "拒答"
        status_class = "status-chip-reject"
    elif flow_status == "follow_up":
        flow_label = "追问"
        status_class = "status-chip-follow-up"
    else:
        flow_label = "未知"
        status_class = "status-chip-unknown"
    preprocess_decision = match.get("preprocess_decision", "")
    preprocess_label = ""
    if preprocess_decision == "data_query":
        preprocess_label = "DataQuery"
    elif preprocess_decision == "reject_request":
        preprocess_label = "RejectRequest"
    elif preprocess_decision == "ask_human":
        preprocess_label = "AskHuman"
    preprocess_chip = (
        f'<span class="status-chip">预处理判定：{escape(preprocess_label)}</span>'
        if preprocess_label
        else ""
    )
    return f"""
    <section class="status-summary">
      <span class="status-chip {status_class}">流程状态：{flow_label}</span>
      {preprocess_chip}
      <span class="status-chip">重试次数：{match.get("retry_count", 0)}</span>
    </section>
    """


def _render_placeholder(skipped: bool = False) -> str:
    if skipped:
        return '<div class="missing">未执行（流程在预处理终止）</div>'
    return '<div class="missing">未命中该字段</div>'


def _render_text_section(title: str, content: str, skipped: bool = False) -> str:
    if not content:
        return f"""
        <section class="section">
          <h3>{escape(title)}</h3>
          {_render_placeholder(skipped)}
        </section>
        """
    return f"""
    <section class="section">
      <h3>{escape(title)}</h3>
      <pre>{escape(content)}</pre>
    </section>
    """


def _render_collapsible_text_section(title: str, content: str, skipped: bool = False) -> str:
    if not content:
        return _render_text_section(title, content, skipped=skipped)
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
    skipped: bool = False,
) -> str:
    if not content:
        return _render_text_section(title, content, skipped=skipped)
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


def _render_collapsible_copyable_text_section(
    title: str,
    content: str,
    target_id: str,
    skipped: bool = False,
) -> str:
    if not content:
        return _render_text_section(title, content, skipped=skipped)
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
    skipped: bool = False,
) -> str:
    if not content:
        return _render_text_section(title, content, skipped=skipped)
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


def _render_sql_rewrite_section(
    title: str,
    rewritten_question: str,
    target_id: str,
    prompt_raw: str,
    prompt_json: str,
    skipped: bool = False,
) -> str:
    display_content = rewritten_question or prompt_json or prompt_raw
    if not display_content:
        return _render_text_section(title, "", skipped=skipped)
    prompt_button = ""
    prompt_payload = ""
    if prompt_json:
        prompt_button = (
            f'<button type="button" class="copy-btn copy-json-btn" '
            f'data-copy-target="{escape(target_id)}-prompt-json" '
            f'onclick="copySection(this)" title="复制提示词 JSON">Prompt</button>'
        )
        prompt_payload = f'<pre id="{escape(target_id)}-prompt-json" hidden>{escape(prompt_json)}</pre>'
    question_button = ""
    if rewritten_question:
        question_button = (
            f'<button type="button" class="copy-btn copy-json-btn" '
            f'data-copy-target="{escape(target_id)}" '
            f'onclick="copySection(this)" title="复制改写问题">问题</button>'
        )
    return f"""
    <section class="section">
      <div class="section-header">
        <h3>{escape(title)}</h3>
        <div class="copy-actions">
          {prompt_button}
          {question_button}
          <span class="copy-feedback" aria-live="polite">已复制</span>
        </div>
      </div>
      <pre id="{escape(target_id)}">{escape(display_content)}</pre>
      {prompt_payload}
    </section>
    """


def _render_grouped_knowledge_section(
    title: str,
    groups: list[tuple[str, str]],
    skipped: bool = False,
) -> str:
    if skipped:
        return _render_text_section(title, "", skipped=True)

    cards = []
    has_any = False
    for label, content in groups:
        normalized = str(content).strip()
        if normalized:
            has_any = True
            body = f'<pre class="knowledge-pre">{escape(normalized)}</pre>'
        else:
            body = _render_placeholder(False)
        cards.append(
            f'<div class="knowledge-item"><h4>{escape(label)}</h4>{body}</div>'
        )

    if not cards:
        return _render_text_section(title, "", skipped=skipped)
    if not has_any:
        return f"""
        <section class="section">
          <h3>{escape(title)}</h3>
          {_render_placeholder(False)}
        </section>
        """
    return f"""
    <section class="section">
      <h3>{escape(title)}</h3>
      <div class="knowledge-group">{''.join(cards)}</div>
    </section>
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


def _render_list_section(
    title: str,
    items: list[str],
    kind: str | None = None,
    skipped: bool = False,
) -> str:
    if not items:
        return f"""
        <section class="section">
          <h3>{escape(title)}</h3>
          {_render_placeholder(skipped)}
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


def _render_collapsible_list_section(
    title: str,
    items: list[str],
    kind: str | None = None,
    skipped: bool = False,
) -> str:
    if not items:
        return _render_list_section(title, items, kind, skipped=skipped)
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


def _format_knowledge_bundle(bundle: dict[str, Any] | None) -> str:
    if not isinstance(bundle, dict):
        return ""
    lines = []
    mappings = [
        ("global_result", "全局结果"),
        ("scope_result", "作用域结果"),
    ]
    for key, label in mappings:
        value = str(bundle.get(key, "")).strip()
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)
