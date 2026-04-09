from __future__ import annotations

from collections import Counter
import json
from html import escape
from typing import Any


FLOW_NODE_SPECS = [
    {"key": "start", "label": "开始", "meta": "起始", "type": "start"},
    {"key": "ac_enriched_question", "label": "实体检索", "meta": "", "type": "process"},
    {"key": "preprocess_knowledge", "label": "拒答/追问知识", "meta": "", "type": "process"},
    {"key": "preprocess_decision", "label": "拒答/追问判定", "meta": "判断", "type": "decision"},
    {"key": "mask_question", "label": "标准化问题", "meta": "", "type": "process"},
    {"key": "sql_knowledge", "label": "检索SQL生成知识", "meta": "", "type": "process"},
    {"key": "sql_rewrite", "label": "问题改写", "meta": "", "type": "process"},
    {"key": "recalled_tables", "label": "表检索", "meta": "", "type": "process"},
    {"key": "final_prompt", "label": "拼装Prompt", "meta": "", "type": "process"},
    {"key": "generated_ir", "label": "生成 IR", "meta": "", "type": "process"},
    {"key": "verifier", "label": "校验", "meta": "判断", "type": "decision"},
    {"key": "end", "label": "结束", "meta": "结果", "type": "end"},
]


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
    flow_views = []
    active_flow_anchor = ""
    for question_index, question_group in enumerate(report["questions"], start=1):
        question_anchor_id = f"question-{question_index}"
        question_label = question_group["question"]
        match_nav_items = []
        for match in question_group["matches"]:
            anchor_id = f"{question_anchor_id}-match-{match['index']}"
            if not active_flow_anchor:
                active_flow_anchor = anchor_id
            match_nav_items.append(f"<li>{_render_nav_match_link(anchor_id, match, question_anchor_id)}</li>")
            flow_views.append(_render_flow_view(anchor_id, match, active=anchor_id == active_flow_anchor))
        nested_nav = f"<ul>{''.join(match_nav_items)}</ul>" if match_nav_items else ""
        nav_items.append(
            f'<li><a class="nav-question-link" data-question-anchor="{escape(question_anchor_id)}" '
            f'href="#{question_anchor_id}">{escape(question_label)}</a>{nested_nav}</li>'
        )
        detail_sections.append(_render_question_group(question_anchor_id, question_group))

    nav_html = "".join(nav_items) if nav_items else "<li>未发现任何问题</li>"
    details_html = "".join(detail_sections) if detail_sections else "<section class=\"empty\">未发现任何问题。</section>"
    flow_stage_html = _render_flow_stage("".join(flow_views), active_flow_anchor)

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
      grid-template-columns: 260px minmax(0, 1fr);
      gap: 12px;
      align-items: start;
    }}
    .layout.layout-flow-hidden {{
      grid-template-columns: 260px minmax(0, 1fr);
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
    .nav a.nav-question-active {{
      background: #edf5ff;
      border-color: #bfd3f3;
      color: #1f4f89;
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
    .workspace {{
      position: sticky;
      top: 12px;
      max-height: calc(100vh - 24px);
      min-width: 0;
    }}
    .workspace-shell {{
      display: grid;
      grid-template-rows: auto 1fr;
      min-height: calc(100vh - 24px);
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 18px;
      box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
      overflow: hidden;
    }}
    .content-tabs {{
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 12px;
      border-bottom: 1px solid #e3eaf4;
      background: linear-gradient(180deg, #ffffff 0%, #f3f7ff 100%);
    }}
    .content-tabs-title {{
      margin-right: auto;
      font-size: 13px;
      font-weight: 700;
      color: #334a67;
    }}
    .content-tab {{
      height: 30px;
      padding: 0 12px;
      border: 1px solid #d1dceb;
      border-radius: 999px;
      background: #ffffff;
      color: #41566f;
      font-size: 12px;
      font-weight: 700;
      cursor: pointer;
    }}
    .content-tab[hidden] {{
      display: none;
    }}
    .content-tab.content-tab-active {{
      background: #e8f5f2;
      border-color: #9ad8cb;
      color: var(--accent);
    }}
    .content-panels {{
      display: grid;
      min-width: 0;
      min-height: 0;
    }}
    .content-panel[hidden] {{
      display: none;
    }}
    .content-panel-body {{
      min-height: 0;
      max-height: calc(100vh - 92px);
      overflow: auto;
      padding: 12px;
      box-sizing: border-box;
      scrollbar-width: none;
      -ms-overflow-style: none;
    }}
    .content-panel-body::-webkit-scrollbar {{
      width: 0;
      height: 0;
      display: none;
    }}
    .detail-column {{
      display: grid;
      gap: 14px;
      min-width: 0;
    }}
    .flow-stage {{
      display: grid;
      gap: 8px;
      min-width: 0;
      --flow-svg-scale: 82%;
    }}
    .flow-stage[hidden] {{
      display: none;
    }}
    .flow-stage-body {{
      position: relative;
      padding: 0;
      overflow: visible;
    }}
    .flow-stage-toolbar {{
      display: flex;
      justify-content: flex-end;
      align-items: center;
      gap: 6px;
    }}
    .flow-stage-controls {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 6px;
      border: 1px solid #d9e2ef;
      border-radius: 999px;
      background: #f8fbff;
    }}
    .flow-zoom-button {{
      border: 1px solid #c8d5e6;
      border-radius: 999px;
      background: #ffffff;
      color: #29425b;
      font-size: 11px;
      font-weight: 700;
      line-height: 1;
      padding: 5px 9px;
      cursor: pointer;
    }}
    .flow-zoom-button:hover {{
      background: #eef5ff;
    }}
    .flow-zoom-value {{
      min-width: 40px;
      text-align: center;
      color: #51667f;
      font-size: 11px;
      font-weight: 700;
    }}
    .flow-stage-canvas {{
      display: grid;
      gap: 8px;
    }}
    .flow-view {{
      display: grid;
      gap: 8px;
    }}
    .flow-view[hidden] {{
      display: none;
    }}
    .flow-view-title {{
      padding: 5px 8px;
      border: 1px solid #dce5f2;
      border-radius: 12px;
      background: #f8fbff;
      color: #334a67;
      font-size: 10px;
      line-height: 1.45;
    }}
    .flow-svg-wrap {{
      position: relative;
      border: 1px solid #d9e2ef;
      border-radius: 16px;
      background: #ffffff;
      padding: 4px 4px 8px;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
    }}
    .flow-svg {{
      display: block;
      width: var(--flow-svg-scale, 82%);
      height: auto;
      margin: 0 auto;
    }}
    .flow-svg .flow-edge-label {{
      pointer-events: none;
    }}
    .flow-svg .flow-edge-label-text {{
      fill: #41566f;
      font-size: 11px;
      font-weight: 700;
      text-anchor: middle;
      dominant-baseline: middle;
    }}
    .flow-svg .flow-group-box {{
      fill: rgba(209, 225, 248, 0.22);
      stroke: #a8bad6;
      stroke-width: 1.2;
      stroke-dasharray: 6 5;
    }}
    .flow-svg .flow-group-title {{
      fill: #5f738e;
      font-size: 12px;
      font-weight: 700;
    }}
    .flow-svg .flow-node-shape {{
      stroke-width: 1.5;
      transition: fill 0.16s ease, stroke 0.16s ease, filter 0.16s ease;
    }}
    .flow-svg .flow-node-text {{
      fill: #243447;
      font-size: 11px;
      font-weight: 700;
      text-anchor: middle;
      dominant-baseline: middle;
      pointer-events: none;
    }}
    .flow-svg .flow-node-subtext {{
      fill: #607086;
      font-size: 9px;
      font-weight: 600;
      text-anchor: middle;
      dominant-baseline: middle;
      pointer-events: none;
    }}
    .flow-svg .flow-connector-line {{
      stroke: #99a8bb;
      stroke-width: 1.6;
      fill: none;
    }}
    .flow-svg .flow-connector-active {{
      stroke: #111827;
      stroke-width: 2.6;
    }}
    .flow-svg .flow-connector-unknown {{
      stroke: #c7d0dc;
    }}
    .flow-svg .flow-connector-success {{
      stroke: #52b694;
    }}
    .flow-svg .flow-connector-failed {{
      stroke: #cf5d5d;
    }}
    .flow-svg .flow-connector-reject {{
      stroke: #d6a640;
    }}
    .flow-svg .flow-connector-follow-up {{
      stroke: #6b9bf0;
    }}
    .flow-svg .flow-node-hitbox {{
      fill: transparent;
      cursor: pointer;
    }}
    .flow-svg .flow-node.flow-node-complete .flow-node-shape {{
      fill: #effbf7;
      stroke: #87cdb8;
    }}
    .flow-svg .flow-node.flow-node-success .flow-node-shape {{
      fill: #dcf6ed;
      stroke: #45b28d;
    }}
    .flow-svg .flow-node.flow-node-failed .flow-node-shape {{
      fill: #ffe5e5;
      stroke: #cf5d5d;
    }}
    .flow-svg .flow-node.flow-node-reject .flow-node-shape {{
      fill: #fff2cf;
      stroke: #d6a640;
    }}
    .flow-svg .flow-node.flow-node-follow-up .flow-node-shape {{
      fill: #e5efff;
      stroke: #6b9bf0;
    }}
    .flow-svg .flow-node.flow-node-unknown .flow-node-shape {{
      fill: #eef2f7;
      stroke: #b8c2cf;
    }}
    .flow-svg .flow-node.flow-node-active .flow-node-shape {{
      filter: drop-shadow(0 0 0.45rem rgba(15, 118, 110, 0.18));
      stroke-width: 2;
    }}
    .flow-tooltip-popup {{
      position: absolute;
      min-width: 220px;
      max-width: min(320px, calc(100% - 20px));
      border: 1px solid #d2dceb;
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.98);
      box-shadow: 0 18px 34px rgba(15, 23, 42, 0.18);
      overflow: hidden;
      z-index: 24;
    }}
    .flow-tooltip-popup[hidden] {{
      display: none;
    }}
    .flow-tooltip-title {{
      padding: 10px 12px 8px;
      border-bottom: 1px solid #e5edf7;
      background: #f7faff;
      color: #324a68;
      font-size: 12px;
      font-weight: 700;
    }}
    .flow-tooltip-popup pre {{
      max-height: 220px;
      margin: 0;
      padding: 12px;
      border-radius: 0;
      background: transparent;
      color: #223247;
      overflow: auto;
      white-space: pre-wrap;
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
    .config-item.config-hidden {{
      display: none !important;
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
    .settings-fab {{
      position: fixed;
      right: 14px;
      bottom: 14px;
      z-index: 40;
      height: 32px;
      padding: 0 12px;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: #f8fbff;
      color: #27405f;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 6px 18px rgba(15, 23, 42, 0.12);
    }}
    .settings-fab:hover {{
      background: #edf5ff;
    }}
    .settings-panel {{
      position: fixed;
      right: 14px;
      bottom: 54px;
      width: 280px;
      max-height: min(70vh, 560px);
      z-index: 41;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: #ffffff;
      box-shadow: 0 16px 32px rgba(15, 23, 42, 0.18);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    .settings-panel[hidden] {{
      display: none;
    }}
    .settings-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      background: #f7faff;
    }}
    .settings-header strong {{
      font-size: 13px;
      color: #334a67;
    }}
    .settings-close {{
      width: 24px;
      height: 24px;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: #ffffff;
      color: #516074;
      cursor: pointer;
      font-size: 14px;
      line-height: 1;
    }}
    .settings-list {{
      display: grid;
      gap: 2px;
      padding: 8px;
      overflow-y: auto;
    }}
    .settings-item {{
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 8px;
      border-radius: 8px;
      color: #334155;
      font-size: 13px;
      cursor: pointer;
      user-select: none;
    }}
    .settings-item:hover {{
      background: #f2f7ff;
    }}
    .settings-item input {{
      margin: 0;
      width: 14px;
      height: 14px;
      accent-color: var(--accent);
    }}
    @media (max-width: 960px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}
      .layout.layout-flow-hidden {{
        grid-template-columns: 1fr;
      }}
      .nav {{
        position: static;
        max-height: none;
        overflow-y: visible;
      }}
      .workspace {{
        position: static;
        max-height: none;
      }}
      .workspace-shell {{
        min-height: auto;
      }}
      .content-panel-body {{
        max-height: none;
      }}
      .settings-fab {{
        right: 10px;
        bottom: 10px;
      }}
      .settings-panel {{
        right: 10px;
        left: 10px;
        width: auto;
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
      <section class="workspace">
        <section class="workspace-shell">
          <div class="content-tabs">
            <div class="content-tabs-title">流程 / 详情</div>
            <button type="button" id="content-tab-flow" class="content-tab content-tab-active" data-tab-key="flow">流程</button>
            <button type="button" id="content-tab-details" class="content-tab" data-tab-key="details">详情</button>
          </div>
          <div class="content-panels">
            <section id="content-panel-flow" class="content-panel" data-tab-panel="flow">
              <div id="flow-panel-body" class="content-panel-body">{flow_stage_html}</div>
            </section>
            <section id="content-panel-details" class="content-panel" data-tab-panel="details" hidden>
              <div id="details-panel-body" class="content-panel-body">
                <main class="detail-column">{details_html}</main>
              </div>
            </section>
          </div>
        </section>
      </section>
    </div>
  </div>
  <button type="button" id="settings-toggle" class="settings-fab" aria-controls="settings-panel" aria-expanded="false">设置</button>
  <aside id="settings-panel" class="settings-panel" hidden>
    <div class="settings-header">
      <strong>详情展示项</strong>
      <button type="button" id="settings-close" class="settings-close" aria-label="关闭设置">×</button>
    </div>
    <div id="settings-list" class="settings-list"></div>
  </aside>
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

    const DETAIL_FIELD_OPTIONS = [
      {{ key: 'flow_diagram', label: '流程图' }},
      {{ key: 'status_summary', label: '流程状态' }},
      {{ key: 'anchor_line', label: '命中锚点日志' }},
      {{ key: 'ac_enriched_question', label: '实体检索' }},
      {{ key: 'preprocess_rewritten_question', label: '拒答/追问改写' }},
      {{ key: 'preprocess_knowledge', label: '拒答/追问知识' }},
      {{ key: 'mask_question', label: '标准化问题' }},
      {{ key: 'sql_knowledge', label: '检索SQL生成知识' }},
      {{ key: 'sql_rewrite', label: '问题改写' }},
      {{ key: 'recalled_tables', label: '表检索结果' }},
      {{ key: 'ir_table_definition', label: 'IR 表定义' }},
      {{ key: 'final_prompt', label: '拼装Prompt' }},
      {{ key: 'verifier_records', label: '校验记录' }},
      {{ key: 'generated_ir', label: '生成 IR 结果' }},
      {{ key: 'complete_ir', label: '完整 IR' }},
      {{ key: 'parse_errors', label: '解析错误' }},
    ];
    const DETAIL_FIELD_STORAGE_KEY = 'chatbi_report_detail_fields_v1';
    const FLOW_ZOOM_STORAGE_KEY = 'chatbi_report_flow_zoom_v1';
    const FLOW_ZOOM_DEFAULT = 0.82;
    const FLOW_ZOOM_MIN = 0.55;
    const FLOW_ZOOM_MAX = 1.2;
    const FLOW_ZOOM_STEP = 0.05;
    let detailFieldVisibility = {{}};
    let navSyncTicking = false;
    let activeContentTab = 'flow';
    let flowZoom = FLOW_ZOOM_DEFAULT;

    function getDefaultDetailVisibility() {{
      const defaults = {{}};
      DETAIL_FIELD_OPTIONS.forEach((option) => {{
        defaults[option.key] = true;
      }});
      return defaults;
    }}

    function loadDetailVisibility() {{
      const defaults = getDefaultDetailVisibility();
      try {{
        const raw = window.localStorage.getItem(DETAIL_FIELD_STORAGE_KEY);
        if (!raw) {{
          return defaults;
        }}
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {{
          return defaults;
        }}
        const merged = {{ ...defaults }};
        for (const option of DETAIL_FIELD_OPTIONS) {{
          if (typeof parsed[option.key] === 'boolean') {{
            merged[option.key] = parsed[option.key];
          }}
        }}
        return merged;
      }} catch (error) {{
        return defaults;
      }}
    }}

    function saveDetailVisibility() {{
      try {{
        window.localStorage.setItem(DETAIL_FIELD_STORAGE_KEY, JSON.stringify(detailFieldVisibility));
      }} catch (error) {{
      }}
    }}

    function clampFlowZoom(value) {{
      return Math.min(FLOW_ZOOM_MAX, Math.max(FLOW_ZOOM_MIN, value));
    }}

    function loadFlowZoom() {{
      try {{
        const raw = window.localStorage.getItem(FLOW_ZOOM_STORAGE_KEY);
        if (!raw) {{
          return FLOW_ZOOM_DEFAULT;
        }}
        const parsed = Number.parseFloat(raw);
        return Number.isFinite(parsed) ? clampFlowZoom(parsed) : FLOW_ZOOM_DEFAULT;
      }} catch (error) {{
        return FLOW_ZOOM_DEFAULT;
      }}
    }}

    function saveFlowZoom() {{
      try {{
        window.localStorage.setItem(FLOW_ZOOM_STORAGE_KEY, String(flowZoom));
      }} catch (error) {{
      }}
    }}

    function applyFlowZoom() {{
      const flowStage = document.getElementById('flow-stage');
      const value = document.getElementById('flow-zoom-value');
      if (flowStage) {{
        flowStage.style.setProperty('--flow-svg-scale', `${{Math.round(flowZoom * 100)}}%`);
      }}
      if (value) {{
        value.textContent = `${{Math.round(flowZoom * 100)}}%`;
      }}
    }}

    function setFlowZoom(nextZoom) {{
      flowZoom = clampFlowZoom(nextZoom);
      applyFlowZoom();
      saveFlowZoom();
    }}

    function bindFlowZoomControls() {{
      flowZoom = loadFlowZoom();
      applyFlowZoom();
      const zoomOut = document.getElementById('flow-zoom-out');
      const zoomIn = document.getElementById('flow-zoom-in');
      const zoomReset = document.getElementById('flow-zoom-reset');
      if (zoomOut) {{
        zoomOut.addEventListener('click', () => setFlowZoom(flowZoom - FLOW_ZOOM_STEP));
      }}
      if (zoomIn) {{
        zoomIn.addEventListener('click', () => setFlowZoom(flowZoom + FLOW_ZOOM_STEP));
      }}
      if (zoomReset) {{
        zoomReset.addEventListener('click', () => setFlowZoom(1));
      }}
    }}

    function applyDetailVisibility() {{
      const blocks = document.querySelectorAll('.config-item[data-field-key]');
      blocks.forEach((block) => {{
        const key = block.getAttribute('data-field-key');
        const visible = key ? detailFieldVisibility[key] !== false : true;
        block.classList.toggle('config-hidden', !visible);
      }});
      const layout = document.querySelector('.layout');
      const flowStage = document.getElementById('flow-stage');
      const flowTab = document.getElementById('content-tab-flow');
      const flowPanel = document.getElementById('content-panel-flow');
      const flowVisible = detailFieldVisibility.flow_diagram !== false;
      if (layout) {{
        layout.classList.toggle('layout-flow-hidden', !flowVisible);
      }}
      if (flowStage) {{
        if (flowVisible) {{
          flowStage.removeAttribute('hidden');
        }} else {{
          flowStage.setAttribute('hidden', '');
        }}
      }}
      if (flowTab) {{
        flowTab.hidden = !flowVisible;
      }}
      if (flowPanel) {{
        flowPanel.hidden = !flowVisible || activeContentTab !== 'flow';
      }}
      if (!flowVisible && activeContentTab === 'flow') {{
        setActiveContentTab('details');
      }}
    }}

    function renderSettingsList() {{
      const container = document.getElementById('settings-list');
      if (!container) {{
        return;
      }}
      const items = DETAIL_FIELD_OPTIONS.map((option) => {{
        const checked = detailFieldVisibility[option.key] !== false;
        const checkedAttr = checked ? ' checked' : '';
        return (
          `<label class="settings-item">` +
          `<input type="checkbox" data-field-key="${{option.key}}"${{checkedAttr}} />` +
          `<span>${{option.label}}</span>` +
          `</label>`
        );
      }});
      container.innerHTML = items.join('');
      container.querySelectorAll('input[type="checkbox"][data-field-key]').forEach((input) => {{
        input.addEventListener('change', () => {{
          const fieldKey = input.getAttribute('data-field-key');
          if (!fieldKey) {{
            return;
          }}
          detailFieldVisibility[fieldKey] = input.checked;
          saveDetailVisibility();
          applyDetailVisibility();
        }});
      }});
    }}

    function setSettingsPanelOpen(open) {{
      const panel = document.getElementById('settings-panel');
      const toggle = document.getElementById('settings-toggle');
      if (!panel || !toggle) {{
        return;
      }}
      if (open) {{
        panel.removeAttribute('hidden');
        toggle.setAttribute('aria-expanded', 'true');
      }} else {{
        panel.setAttribute('hidden', '');
        toggle.setAttribute('aria-expanded', 'false');
      }}
    }}

    function initSettingsPanel() {{
      detailFieldVisibility = loadDetailVisibility();
      applyDetailVisibility();
      renderSettingsList();
      const toggle = document.getElementById('settings-toggle');
      const close = document.getElementById('settings-close');
      const panel = document.getElementById('settings-panel');
      if (toggle) {{
        toggle.addEventListener('click', (event) => {{
          event.stopPropagation();
          const shouldOpen = toggle.getAttribute('aria-expanded') !== 'true';
          setSettingsPanelOpen(shouldOpen);
        }});
      }}
      if (close) {{
        close.addEventListener('click', () => {{
          setSettingsPanelOpen(false);
        }});
      }}
      document.addEventListener('click', (event) => {{
        if (!panel || panel.hasAttribute('hidden')) {{
          return;
        }}
        const target = event.target;
        if (!(target instanceof Node)) {{
          return;
        }}
        if (panel.contains(target) || (toggle && toggle.contains(target))) {{
          return;
        }}
        setSettingsPanelOpen(false);
      }});
      document.addEventListener('keydown', (event) => {{
        if (event.key === 'Escape') {{
          setSettingsPanelOpen(false);
          closeOpenFlowTooltips();
        }}
      }});
    }}

    function closeOpenFlowTooltips() {{
      const popup = document.getElementById('flow-tooltip-popup');
      if (popup) {{
        popup.setAttribute('hidden', '');
      }}
      document.querySelectorAll('.flow-svg .flow-node.flow-node-active').forEach((node) => {{
        node.classList.remove('flow-node-active');
      }});
    }}

    function showFlowTooltip(node, event) {{
      const popup = document.getElementById('flow-tooltip-popup');
      const title = document.getElementById('flow-tooltip-title');
      const content = document.getElementById('flow-tooltip-content');
      const stageBody = document.getElementById('flow-stage-body');
      if (!popup || !title || !content || !stageBody || !node) {{
        return;
      }}
      closeOpenFlowTooltips();
      node.classList.add('flow-node-active');
      title.textContent = node.getAttribute('data-node-title') || '';
      content.textContent = node.getAttribute('data-node-summary') || '';
      popup.removeAttribute('hidden');

      const bodyRect = stageBody.getBoundingClientRect();
      const nodeRect = node.getBoundingClientRect();
      const top = nodeRect.top - bodyRect.top + stageBody.scrollTop + Math.min(24, nodeRect.height / 2);
      const left = Math.max(8, Math.min(bodyRect.width - popup.offsetWidth - 8, nodeRect.right - bodyRect.left + 8));
      popup.style.top = `${{top}}px`;
      popup.style.left = `${{left}}px`;
    }}

    function bindFlowNodeEvents() {{
      document.querySelectorAll('.flow-svg [data-flow-node="true"]').forEach((node) => {{
        node.addEventListener('mouseenter', (event) => showFlowTooltip(node, event));
        node.addEventListener('focusin', (event) => showFlowTooltip(node, event));
        node.addEventListener('click', (event) => {{
          event.preventDefault();
          event.stopPropagation();
          showFlowTooltip(node, event);
        }});
      }});
    }}

    function setActiveContentTab(tabKey = 'flow') {{
      const flowVisible = detailFieldVisibility.flow_diagram !== false;
      const currentMatchAnchor = getActiveMatchAnchorFromViewport();
      const normalized = tabKey === 'details' ? 'details' : 'flow';
      activeContentTab = !flowVisible && normalized === 'flow' ? 'details' : normalized;
      document.querySelectorAll('.content-tab[data-tab-key]').forEach((button) => {{
        const key = button.getAttribute('data-tab-key');
        const selected = key === activeContentTab;
        button.classList.toggle('content-tab-active', selected);
        button.setAttribute('aria-selected', selected ? 'true' : 'false');
      }});
      document.querySelectorAll('.content-panel[data-tab-panel]').forEach((panel) => {{
        const key = panel.getAttribute('data-tab-panel');
        panel.hidden = key !== activeContentTab || (key === 'flow' && !flowVisible);
      }});
      if (activeContentTab === 'details' && currentMatchAnchor) {{
        scrollDetailsToAnchor(currentMatchAnchor);
        syncActivePanels();
      }} else if (activeContentTab === 'details') {{
        syncActivePanels();
      }}
    }}

    function bindContentTabs() {{
      document.querySelectorAll('.content-tab[data-tab-key]').forEach((button) => {{
        button.addEventListener('click', () => {{
          const key = button.getAttribute('data-tab-key') || 'flow';
          setActiveContentTab(key);
        }});
      }});
    }}

    function getOrderedMatchAnchors() {{
      return Array.from(document.querySelectorAll('.match[id]')).map((section) => section.id);
    }}

    function getAdjacentMatchAnchor(anchorId = '', offset = 0) {{
      if (!anchorId || !offset) {{
        return '';
      }}
      const anchors = getOrderedMatchAnchors();
      const currentIndex = anchors.indexOf(anchorId);
      if (currentIndex < 0) {{
        return '';
      }}
      const nextIndex = currentIndex + offset;
      if (nextIndex < 0 || nextIndex >= anchors.length) {{
        return '';
      }}
      return anchors[nextIndex];
    }}

    function activateMatchAnchor(anchorId = '', options = {{ preserveTab: true, scrollDetails: false, resetFlowScroll: true }}) {{
      const resolvedMatchAnchor = resolveMatchAnchor(anchorId) || anchorId;
      if (!resolvedMatchAnchor) {{
        return;
      }}
      if (window.location.hash !== `#${{resolvedMatchAnchor}}`) {{
        window.history.replaceState(null, '', `#${{resolvedMatchAnchor}}`);
      }}
      updateActiveNavLinks(resolvedMatchAnchor);
      setActiveFlowView(resolvedMatchAnchor, options.resetFlowScroll !== false);
      if (options.preserveTab === false) {{
        setActiveContentTab('details');
      }} else {{
        setActiveContentTab(activeContentTab);
      }}
      if (options.scrollDetails) {{
        window.requestAnimationFrame(() => {{
          scrollDetailsToAnchor(resolvedMatchAnchor);
          syncActivePanels();
        }});
      }}
    }}

    function bindFlowStageNavigation() {{
      const flowPanelBody = document.getElementById('flow-panel-body');
      if (!flowPanelBody) {{
        return;
      }}
      flowPanelBody.addEventListener('wheel', (event) => {{
        if (activeContentTab !== 'flow') {{
          return;
        }}
        const willReachBottom =
          flowPanelBody.scrollTop + flowPanelBody.clientHeight + Math.max(event.deltaY, 0) >= flowPanelBody.scrollHeight - 2;
        const willReachTop = flowPanelBody.scrollTop + Math.min(event.deltaY, 0) <= 0;
        let nextAnchor = '';
        if (event.deltaY > 0 && willReachBottom) {{
          nextAnchor = getAdjacentMatchAnchor(getActiveMatchAnchorFromViewport(), 1);
        }} else if (event.deltaY < 0 && willReachTop) {{
          nextAnchor = getAdjacentMatchAnchor(getActiveMatchAnchorFromViewport(), -1);
        }}
        if (!nextAnchor) {{
          return;
        }}
        event.preventDefault();
        activateMatchAnchor(nextAnchor, {{ preserveTab: true, scrollDetails: false, resetFlowScroll: true }});
      }}, {{ passive: false }});
    }}

    function scrollDetailsToAnchor(anchorId = '') {{
      if (!anchorId) {{
        return;
      }}
      const target = document.getElementById(anchorId);
      if (!target) {{
        return;
      }}
      target.scrollIntoView({{ block: 'start', behavior: 'auto' }});
    }}

    function bindNavLinkBehavior() {{
      document.querySelectorAll('.nav a[href^="#"]').forEach((link) => {{
        link.addEventListener('click', (event) => {{
          const href = link.getAttribute('href') || '';
          const targetId = href.startsWith('#') ? href.slice(1) : '';
          if (!targetId) {{
            return;
          }}
          event.preventDefault();
          const resolvedMatchAnchor = resolveMatchAnchor(targetId);
          if (resolvedMatchAnchor) {{
            activateMatchAnchor(resolvedMatchAnchor, {{
              preserveTab: true,
              scrollDetails: activeContentTab === 'details',
              resetFlowScroll: true,
            }});
          }} else {{
            if (window.location.hash !== `#${{targetId}}`) {{
              window.history.replaceState(null, '', `#${{targetId}}`);
            }}
            updateActiveNavLinks(targetId);
            if (activeContentTab === 'details') {{
              window.requestAnimationFrame(() => {{
                scrollDetailsToAnchor(targetId);
                syncActivePanels();
              }});
            }} else {{
              const firstMatchAnchor = resolveMatchAnchor(targetId);
              if (firstMatchAnchor) {{
                activateMatchAnchor(firstMatchAnchor, {{ preserveTab: true, scrollDetails: false, resetFlowScroll: true }});
              }}
            }}
          }}
        }});
      }});
    }}

    function scrollNavIntoView(link) {{
      const nav = document.querySelector('.nav');
      if (!nav || !link) {{
        return;
      }}
      const navRect = nav.getBoundingClientRect();
      const linkRect = link.getBoundingClientRect();
      if (linkRect.top < navRect.top || linkRect.bottom > navRect.bottom) {{
        link.scrollIntoView({{ block: 'nearest' }});
      }}
    }}

    function updateActiveNavLinks(anchorId = '') {{
      const nav = document.querySelector('.nav');
      if (!nav) {{
        return;
      }}
      const links = Array.from(nav.querySelectorAll('a[href^="#"]'));
      links.forEach((link) => {{
        link.classList.remove('nav-active');
        link.classList.remove('nav-parent-active');
        link.classList.remove('nav-question-active');
      }});
      const resolvedAnchorId = anchorId || (window.location.hash ? window.location.hash.slice(1) : '');
      if (!resolvedAnchorId) {{
        return;
      }}
      const expectedHref = `#${{resolvedAnchorId}}`;
      const activeLink = links.find((link) => link.getAttribute('href') === expectedHref);
      if (!activeLink) {{
        return;
      }}
      activeLink.classList.add('nav-active');
      let questionAnchor = activeLink.getAttribute('data-question-anchor') || '';
      if (!questionAnchor) {{
        questionAnchor = activeLink.getAttribute('data-parent-question-anchor') || '';
      }}
      if (questionAnchor) {{
        const questionLink = links.find(
          (link) =>
            link.classList.contains('nav-question-link') &&
            link.getAttribute('data-question-anchor') === questionAnchor,
        );
        if (questionLink) {{
          questionLink.classList.add('nav-question-active');
          if (questionLink !== activeLink) {{
            questionLink.classList.add('nav-parent-active');
          }}
        }}
      }}
      scrollNavIntoView(activeLink);
    }}

    function getActiveMatchAnchorFromViewport() {{
      if (activeContentTab === 'flow') {{
        const flowStage = document.getElementById('flow-stage');
        return flowStage ? flowStage.getAttribute('data-active-match-anchor') || '' : '';
      }}
      const detailPanelBody = document.getElementById('details-panel-body');
      if (!detailPanelBody || detailPanelBody.closest('[hidden]')) {{
        const flowStage = document.getElementById('flow-stage');
        return flowStage ? flowStage.getAttribute('data-active-match-anchor') || '' : '';
      }}
      const sections = Array.from(detailPanelBody.querySelectorAll('.match[id]'));
      if (!sections.length) {{
        return '';
      }}
      const threshold = 96;
      const panelTop = detailPanelBody.getBoundingClientRect().top;
      let active = sections[0].id;
      for (const section of sections) {{
        if (section.getBoundingClientRect().top - panelTop - threshold <= 0) {{
          active = section.id;
        }} else {{
          break;
        }}
      }}
      return active;
    }}

    function resolveMatchAnchor(anchorId = '') {{
      if (!anchorId) {{
        return '';
      }}
      const directMatch = document.getElementById(anchorId);
      if (directMatch && directMatch.classList.contains('match')) {{
        return anchorId;
      }}
      const firstNestedMatch = document.querySelector(`.match[id^="${{CSS.escape(anchorId)}}-match-"]`);
      return firstNestedMatch ? firstNestedMatch.id : '';
    }}

    function setActiveFlowView(anchorId = '', resetScroll = true) {{
      const resolvedAnchorId = resolveMatchAnchor(anchorId) || getActiveMatchAnchorFromViewport();
      const flowStage = document.getElementById('flow-stage');
      const flowStageBody = document.getElementById('flow-stage-body');
      const flowPanelBody = document.getElementById('flow-panel-body');
      if (!flowStage || !resolvedAnchorId) {{
        return;
      }}
      flowStage.setAttribute('data-active-match-anchor', resolvedAnchorId);
      document.querySelectorAll('.flow-view[data-flow-match-anchor]').forEach((view) => {{
        const matches = view.getAttribute('data-flow-match-anchor') === resolvedAnchorId;
        if (matches) {{
          view.removeAttribute('hidden');
        }} else {{
          view.setAttribute('hidden', '');
        }}
      }});
      if (resetScroll) {{
        if (flowStageBody) {{
          flowStageBody.scrollTop = 0;
        }}
        if (flowPanelBody) {{
          flowPanelBody.scrollTop = 0;
        }}
      }}
      closeOpenFlowTooltips();
    }}

    function syncActivePanels() {{
      if (navSyncTicking) {{
        return;
      }}
      navSyncTicking = true;
      window.requestAnimationFrame(() => {{
        const activeMatchAnchor = getActiveMatchAnchorFromViewport();
        updateActiveNavLinks(activeMatchAnchor);
        setActiveFlowView(activeMatchAnchor);
        navSyncTicking = false;
      }});
    }}

    function initializePage() {{
      initSettingsPanel();
      bindFlowZoomControls();
      bindFlowNodeEvents();
      bindContentTabs();
      bindNavLinkBehavior();
      bindFlowStageNavigation();
      const initialAnchor = resolveMatchAnchor(window.location.hash ? window.location.hash.slice(1) : '') || getActiveMatchAnchorFromViewport();
      setActiveContentTab(detailFieldVisibility.flow_diagram !== false ? 'flow' : 'details');
      updateActiveNavLinks(initialAnchor);
      setActiveFlowView(initialAnchor);
      syncActivePanels();
      const detailPanelBody = document.getElementById('details-panel-body');
      if (detailPanelBody) {{
        detailPanelBody.addEventListener('scroll', syncActivePanels, {{ passive: true }});
      }}
      document.addEventListener('click', (event) => {{
        const target = event.target;
        if (!(target instanceof Node)) {{
          return;
        }}
        if (target instanceof Element && target.closest('[data-flow-node="true"]')) {{
          return;
        }}
        closeOpenFlowTooltips();
      }});
    }}

    window.addEventListener('hashchange', () => {{
      const hashAnchor = window.location.hash ? window.location.hash.slice(1) : '';
      const resolvedMatchAnchor = resolveMatchAnchor(hashAnchor);
      if (resolvedMatchAnchor) {{
        activateMatchAnchor(resolvedMatchAnchor, {{
          preserveTab: true,
          scrollDetails: activeContentTab === 'details',
          resetFlowScroll: true,
        }});
      }} else {{
        syncActivePanels();
      }}
    }});
    window.addEventListener('resize', syncActivePanels);
    window.addEventListener('DOMContentLoaded', initializePage);
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
        f"<li><strong>{count}次</strong> {escape(reason)}</li>"
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


def _render_flow_stage(flow_views_html: str, active_flow_anchor: str) -> str:
    if not flow_views_html:
        return """
        <section id="flow-stage" class="flow-stage" hidden></section>
        """
    return f"""
    <section id="flow-stage" class="flow-stage" data-active-match-anchor="{escape(active_flow_anchor)}">
      <div class="flow-stage-toolbar">
        <div id="flow-zoom-controls" class="flow-stage-controls" aria-label="流程图缩放">
          <button id="flow-zoom-out" class="flow-zoom-button" type="button" title="缩小">-</button>
          <span id="flow-zoom-value" class="flow-zoom-value">82%</span>
          <button id="flow-zoom-reset" class="flow-zoom-button" type="button" title="重置">1:1</button>
          <button id="flow-zoom-in" class="flow-zoom-button" type="button" title="放大">+</button>
        </div>
      </div>
      <div id="flow-stage-body" class="flow-stage-body">
        <div id="flow-stage-canvas" class="flow-stage-canvas">
          {flow_views_html}
        </div>
        <div id="flow-tooltip-popup" class="flow-tooltip-popup" hidden>
          <div id="flow-tooltip-title" class="flow-tooltip-title"></div>
          <pre id="flow-tooltip-content"></pre>
        </div>
      </div>
    </section>
    """


def _render_flow_view(anchor_id: str, match: dict[str, Any], active: bool) -> str:
    nodes = _build_flow_nodes(match)
    hidden_attr = "" if active else " hidden"
    svg = _render_flow_svg(anchor_id, match, nodes)
    title = f"{match['anchor_timestamp']} | 第 {match['index']} 次调用"
    return f"""
    <section class="flow-view" data-flow-match-anchor="{escape(anchor_id)}"{hidden_attr}>
      <div class="flow-view-title">{escape(title)}</div>
      <div class="flow-svg-wrap">
        {svg}
      </div>
    </section>
    """


def _render_flow_svg(anchor_id: str, match: dict[str, Any], nodes: list[dict[str, str]]) -> str:
    center_x = 372
    width = 760
    top_padding = 40
    step = 92
    height = top_padding * 2 + step * (len(nodes) - 1) + 78
    positions = {
        node["key"]: {"cx": center_x, "cy": top_padding + index * step}
        for index, node in enumerate(nodes)
    }
    node_parts = []
    connector_parts = []
    node_lookup = {node["key"]: node for node in nodes}

    connector_parts.extend(_render_flow_groups(positions))
    connector_parts.extend(_render_flow_connectors(anchor_id, match, nodes, positions, node_lookup))
    for node in nodes:
        node_parts.append(_render_svg_flow_node(anchor_id, node, positions[node["key"]]["cx"], positions[node["key"]]["cy"]))

    return f"""
    <svg class="flow-svg" viewBox="0 0 {width} {height}" role="img" aria-label="调用流程图">
      <defs>
        <marker id="flow-arrow-head" markerWidth="10" markerHeight="10" refX="7" refY="3.5" orient="auto">
          <polygon points="0 0, 7 3.5, 0 7" fill="context-stroke"></polygon>
        </marker>
      </defs>
      {''.join(connector_parts)}
      {''.join(node_parts)}
    </svg>
    """


def _render_flow_groups(positions: dict[str, dict[str, int]]) -> list[str]:
    groups = [
        ("意图识别", "ac_enriched_question", "preprocess_decision"),
        ("Text2Data-SQL生成", "mask_question", "verifier"),
    ]
    rendered: list[str] = []
    for label, start_key, end_key in groups:
        top = positions[start_key]["cy"] - 38
        bottom = positions[end_key]["cy"] + 42
        rendered.append(
            f"""
            <g class="flow-group">
              <rect class="flow-group-box" x="120" y="{top:.0f}" width="504" height="{bottom - top:.0f}" rx="18" ry="18"></rect>
              <text class="flow-group-title" x="144" y="{top + 18:.0f}">{escape(label)}</text>
            </g>
            """
        )
    return rendered


def _render_svg_flow_node(anchor_id: str, node: dict[str, str], center_x: int, center_y: int) -> str:
    node_id = f"flow-node-{anchor_id}-{node['key'].replace('_', '-')}"
    label = escape(node["label"])
    meta = escape(node["meta"])
    status = escape(node["status"])
    node_type = escape(node["type"])
    summary_attr = _escape_data_attr(node["detail"])
    width, height = _get_flow_node_size(node["type"])
    if node["type"] in {"start", "end"}:
        shape = (
            f'<ellipse class="flow-node-shape" cx="{center_x}" cy="{center_y}" rx="{width / 2:.0f}" ry="{height / 2:.0f}"></ellipse>'
        )
    elif node["type"] == "decision":
        half_width = width / 2
        half_height = height / 2
        shape = (
            f'<polygon class="flow-node-shape" points="{center_x},{center_y - half_height:.0f} '
            f'{center_x + half_width:.0f},{center_y} {center_x},{center_y + half_height:.0f} '
            f'{center_x - half_width:.0f},{center_y}"></polygon>'
        )
    else:
        shape = (
            f'<rect class="flow-node-shape" x="{center_x - width / 2:.0f}" y="{center_y - height / 2:.0f}" '
            f'width="{width:.0f}" height="{height:.0f}" rx="12" ry="12"></rect>'
        )

    return f"""
    <g id="{escape(node_id)}" class="flow-node flow-node-{status} flow-node-{node_type}"
       data-flow-node="true"
       data-node-title="{label}"
       data-node-summary="{summary_attr}">
      {shape}
      <text class="flow-node-text" x="{center_x}" y="{center_y - 7}">{label}</text>
      {"<text class=\"flow-node-subtext\" x=\"" + str(center_x) + "\" y=\"" + str(center_y + 14) + "\">" + meta + "</text>" if meta else ""}
      <rect class="flow-node-hitbox" x="{center_x - width / 2 - 12:.0f}" y="{center_y - height / 2 - 12:.0f}" width="{width + 24:.0f}" height="{height + 24:.0f}" rx="16" ry="16"></rect>
    </g>
    """


def _render_flow_connectors(
    anchor_id: str,
    match: dict[str, Any],
    nodes: list[dict[str, str]],
    positions: dict[str, dict[str, int]],
    node_lookup: dict[str, dict[str, str]],
) -> list[str]:
    connectors: list[str] = []
    main_pairs = [
        ("start", "ac_enriched_question", ""),
        ("ac_enriched_question", "preprocess_knowledge", _short_edge_text(str(match.get("ac_enriched_question", "")).strip(), 18)),
        ("preprocess_knowledge", "preprocess_decision", _compose_preprocess_knowledge_edge_label(match)),
        ("mask_question", "sql_knowledge", _short_edge_text(str(match.get("mask_question", "")).strip(), 18)),
        ("sql_knowledge", "sql_rewrite", _compose_sql_knowledge_edge_label(match)),
        ("sql_rewrite", "recalled_tables", _compose_sql_rewrite_edge_label(match)),
        ("recalled_tables", "final_prompt", _summarize_tables_for_edge(match.get("recalled_tables", []))),
        ("final_prompt", "generated_ir", ""),
        ("generated_ir", "verifier", ""),
    ]

    for from_key, to_key, label in main_pairs:
        status_class = _resolve_linear_connector_status(node_lookup, from_key, to_key)
        connectors.append(
            _render_vertical_connector(
                positions[from_key]["cx"],
                _flow_node_bottom(positions[from_key]["cy"], node_lookup[from_key]["type"]),
                _flow_node_top(positions[to_key]["cy"], node_lookup[to_key]["type"]),
                status_class,
                label,
            )
        )

    preprocess_decision = str(match.get("preprocess_decision", "")).strip()
    data_query_active = preprocess_decision == "data_query"
    reject_active = preprocess_decision == "reject_request"
    follow_up_active = preprocess_decision == "ask_human"
    connectors.append(
        _render_vertical_connector(
            positions["preprocess_decision"]["cx"],
            _flow_node_bottom(positions["preprocess_decision"]["cy"], node_lookup["preprocess_decision"]["type"]),
            _flow_node_top(positions["mask_question"]["cy"], node_lookup["mask_question"]["type"]),
            "active" if data_query_active else "unknown",
            _compose_data_query_edge_label(match) if data_query_active else "问数",
        )
    )
    connectors.append(
        _render_routed_connector(
            [
                (
                    positions["preprocess_decision"]["cx"] + _get_flow_node_size("decision")[0] / 2,
                    positions["preprocess_decision"]["cy"] - 16,
                ),
                (626, positions["preprocess_decision"]["cy"] - 16),
                (626, positions["end"]["cy"] - 40),
                (positions["end"]["cx"] + 94, positions["end"]["cy"] - 40),
                (positions["end"]["cx"] + 94, positions["end"]["cy"] - 10),
            ],
            "active" if reject_active else "unknown",
            "拒答",
            label_x=654,
            label_y=positions["preprocess_decision"]["cy"] - 8,
        )
    )
    connectors.append(
        _render_routed_connector(
            [
                (
                    positions["preprocess_decision"]["cx"] + _get_flow_node_size("decision")[0] / 2,
                    positions["preprocess_decision"]["cy"] + 16,
                ),
                (646, positions["preprocess_decision"]["cy"] + 16),
                (646, positions["end"]["cy"] + 8),
                (positions["end"]["cx"] + 98, positions["end"]["cy"] + 8),
                (positions["end"]["cx"] + 98, positions["end"]["cy"]),
            ],
            "active" if follow_up_active else "unknown",
            "追问",
            label_x=672,
            label_y=positions["preprocess_decision"]["cy"] + 34,
        )
    )

    retry_count = int(match.get("retry_count", 0) or 0)
    if retry_count > 0 or str(match.get("flow_status", "unknown")) == "failed":
        connectors.append(
            _render_routed_connector(
                [
                    (
                        positions["verifier"]["cx"] - 110,
                        positions["verifier"]["cy"],
                    ),
                    (170, positions["verifier"]["cy"]),
                    (170, positions["generated_ir"]["cy"]),
                    (
                        positions["generated_ir"]["cx"] - 128,
                        positions["generated_ir"]["cy"],
                    ),
                ],
                "active" if retry_count > 0 else "unknown",
                f"重试 {retry_count} 次" if retry_count > 0 else "",
                label_x=142,
                label_y=(positions["verifier"]["cy"] + positions["generated_ir"]["cy"]) / 2,
            )
        )

    flow_status = str(match.get("flow_status", "unknown"))
    connectors.append(
        _render_vertical_connector(
            positions["verifier"]["cx"],
            _flow_node_bottom(positions["verifier"]["cy"], node_lookup["verifier"]["type"]),
            _flow_node_top(positions["end"]["cy"], node_lookup["end"]["type"]),
            "active" if flow_status == "success" else "unknown",
            _short_edge_text(_extract_sql_summary(match), 24) if flow_status == "success" else "",
        )
    )
    connectors.append(
        _render_routed_connector(
            [
                (
                    positions["verifier"]["cx"] + 110,
                    positions["verifier"]["cy"],
                ),
                (634, positions["verifier"]["cy"]),
                (634, positions["end"]["cy"] - 34),
                (positions["end"]["cx"] + 94, positions["end"]["cy"] - 34),
                (positions["end"]["cx"] + 94, positions["end"]["cy"]),
            ],
            "active" if flow_status == "failed" else "unknown",
            "最终失败",
            label_x=658,
            label_y=positions["verifier"]["cy"] + 26,
        )
    )

    return connectors


def _render_vertical_connector(center_x: int, start_y: float, end_y: float, status_class: str, label: str = "") -> str:
    path = f"M {center_x} {start_y:.0f} L {center_x} {end_y:.0f}"
    return _render_connector_path(path, status_class, label, center_x + 68, (start_y + end_y) / 2 if label else None)


def _render_routed_connector(
    points: list[tuple[float, float]],
    status_class: str,
    label: str = "",
    *,
    loop: bool = False,
    label_x: float | None = None,
    label_y: float | None = None,
) -> str:
    path = "M " + " L ".join(f"{x:.0f} {y:.0f}" for x, y in points)
    classes = status_class
    if loop:
        classes = f"{classes} loop".strip()
    return _render_connector_path(path, classes, label, label_x, label_y)


def _render_connector_path(path: str, status_class: str, label: str, label_x: float | None, label_y: float | None) -> str:
    class_names = ["flow-connector-line"]
    normalized = status_class.strip()
    if normalized:
        for part in normalized.split():
            if part == "loop":
                class_names.append("flow-connector-loop")
            else:
                class_names.append(f"flow-connector-{part}")
    label_html = ""
    if label and label_x is not None and label_y is not None:
        label_html = _render_edge_label(label, label_x, label_y)
    return (
        f'<g><path class="{" ".join(class_names)}" marker-end="url(#flow-arrow-head)" d="{path}"></path>'
        f"{label_html}</g>"
    )


def _render_edge_label(label: str, x: float, y: float) -> str:
    label_text = escape(label)
    return (
        f'<g class="flow-edge-label" transform="translate({x:.0f},{y:.0f})">'
        f'<text class="flow-edge-label-text" x="0" y="1">{label_text}</text>'
        f"</g>"
    )


def _resolve_linear_connector_status(
    node_lookup: dict[str, dict[str, str]],
    from_key: str,
    to_key: str,
) -> str:
    from_status = node_lookup[from_key]["status"]
    to_status = node_lookup[to_key]["status"]
    if from_status == "unknown" or to_status == "unknown":
        return "unknown"
    if to_status in {"failed", "reject", "follow-up", "success"}:
        return to_status
    return "active"


def _get_flow_node_size(node_type: str) -> tuple[int, int]:
    if node_type in {"start", "end"}:
        return (172, 44)
    if node_type == "decision":
        return (180, 68)
    return (190, 52)


def _flow_node_top(center_y: float, node_type: str) -> float:
    return center_y - _get_flow_node_size(node_type)[1] / 2


def _flow_node_bottom(center_y: float, node_type: str) -> float:
    return center_y + _get_flow_node_size(node_type)[1] / 2


def _summarize_tables_for_edge(items: Any) -> str:
    if not isinstance(items, list):
        return ""
    values = [str(item).strip() for item in items if str(item).strip()]
    if not values:
        return ""
    if len(values) == 1:
        return _short_edge_text(values[0], 18)
    return f"{len(values)}表"


def _short_edge_text(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if not compact or len(compact) > limit:
        return ""
    return compact


def _compose_data_query_edge_label(match: dict[str, Any]) -> str:
    base = "问数"
    rewritten = _short_edge_text(str(match.get("preprocess_rewritten_question", "")).strip(), 18)
    if rewritten:
        return f"{base} {rewritten}"
    return base


def _compose_preprocess_knowledge_edge_label(match: dict[str, Any]) -> str:
    counts = match.get("preprocess_knowledge_counts", {})
    if not isinstance(counts, dict):
        return ""
    global_count = int(counts.get("global", 0) or 0)
    intention_rewrite_count = int(counts.get("intention_rewrite", 0) or 0)
    intention_reject_count = int(counts.get("intention_reject", 0) or 0)
    intention_follow_up_count = int(counts.get("intention_follow_up", 0) or 0)
    return (
        f"Global {global_count} / IntentionRewrite {intention_rewrite_count} / "
        f"IntentionReject {intention_reject_count} / IntentionFollowUp {intention_follow_up_count}"
    )


def _compose_sql_knowledge_edge_label(match: dict[str, Any]) -> str:
    counts = match.get("sql_knowledge_counts", {})
    if not isinstance(counts, dict):
        return ""
    global_count = int(counts.get("global", 0) or 0)
    sql_generation_count = int(counts.get("sql_generation", 0) or 0)
    sql_gen_few_shot_count = int(counts.get("sql_gen_few_shot", 0) or 0)
    return f"Global {global_count} / SQLGeneration {sql_generation_count} / SQLGenFewShot {sql_gen_few_shot_count}"


def _compose_sql_rewrite_edge_label(match: dict[str, Any]) -> str:
    rewritten = _short_edge_text(
        str(match.get("sql_rewritten_question", "") or match.get("rewritten_question", "")).strip(),
        24,
    )
    return rewritten


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
        _wrap_config_item("status_summary", _render_status_summary(match)),
    ]
    sections.extend([
        _wrap_config_item("anchor_line", _render_text_section("命中锚点日志", match["anchor_line"])),
        _wrap_config_item("ac_enriched_question", _render_text_section("实体检索", match.get("ac_enriched_question", ""))),
        _wrap_config_item("preprocess_rewritten_question", _render_text_section("拒答/追问改写", match.get("preprocess_rewritten_question", ""))),
        _wrap_config_item("preprocess_knowledge", _render_grouped_knowledge_section("拒答/追问知识", preprocess_group)),
        _wrap_config_item(
            "mask_question",
            _render_collapsible_text_section(
                "标准化问题",
                match.get("mask_question", ""),
                skipped="mask_question" in skipped_sections,
            ),
        ),
        _wrap_config_item("sql_knowledge", _render_grouped_knowledge_section("检索SQL生成知识", sql_group, skipped=sql_knowledge_skipped)),
        _wrap_config_item(
            "sql_rewrite",
            _render_sql_rewrite_section(
                "问题改写",
                match.get("sql_rewritten_question", "") or match.get("rewritten_question", ""),
                f"sql-rewrite-{anchor_id}",
                match.get("sql_rewrite_prompt_raw", ""),
                match.get("sql_rewrite_prompt_json", ""),
                skipped="sql_rewritten_question" in skipped_sections,
            ),
        ),
        _wrap_config_item(
            "recalled_tables",
            _render_list_section(
                "表检索结果",
                match["recalled_tables"],
                skipped="recalled_tables" in skipped_sections,
            ),
        ),
        _wrap_config_item(
            "ir_table_definition",
            _render_collapsible_text_section(
                "IR 表定义",
                match["ir_table_definition"],
                skipped="ir_table_definition" in skipped_sections,
            ),
        ),
        _wrap_config_item(
            "final_prompt",
            _render_collapsible_prompt_execution_section(
                "拼装Prompt",
                match["final_prompt"].get("combined") or match["final_prompt"].get("raw", ""),
                f"final-prompt-{anchor_id}",
                match_id=match["match_id"],
                executable=bool(match["final_prompt"].get("system") and match["final_prompt"].get("user")),
                prompt=match["final_prompt"],
                skipped="final_prompt" in skipped_sections,
            ),
        ),
        _wrap_config_item(
            "generated_ir",
            _render_collapsible_text_section(
                "生成 IR 结果",
                match["generated_ir"],
                skipped="generated_ir" in skipped_sections,
            ),
        ),
        _wrap_config_item("verifier_records", _render_highlight_list_section("校验记录", match["verifier_failures"], "retry-block")),
        _wrap_config_item(
            "complete_ir",
            _render_copyable_text_section(
                "完整 IR",
                match["complete_ir"],
                f"complete-ir-{anchor_id}",
                show_execute=True,
                match_id=match["match_id"],
                skipped="complete_ir" in skipped_sections,
            ),
        ),
    ])

    if match["parse_errors"]:
        sections.append(_wrap_config_item("parse_errors", _render_list_section("解析错误", match["parse_errors"], kind="errors")))

    return f"""
    <section id="{escape(anchor_id)}" class="match">
      <h2>{escape(title)}</h2>
      <div class="meta">线程 ID：{escape(match['thread_id'])}</div>
      {associated_threads_meta}
      {''.join(sections)}
    </section>
    """


def _build_flow_nodes(match: dict[str, Any]) -> list[dict[str, str]]:
    preprocess_knowledge_text = _format_preprocess_knowledge_tooltip(match.get("preprocess_knowledge", {}))
    sql_knowledge_text = _format_sql_knowledge_tooltip(match.get("sql_knowledge", {}))
    sql_rewrite_text = _format_sql_rewrite_tooltip(match)
    verifier_text = _format_verifier_tooltip(match)
    end_text = _format_end_tooltip(match)

    direct = {
        "start": True,
        "ac_enriched_question": bool(str(match.get("ac_enriched_question", "")).strip()),
        "preprocess_knowledge": bool(preprocess_knowledge_text),
        "preprocess_decision": bool(str(match.get("preprocess_decision", "")).strip()),
        "mask_question": bool(str(match.get("mask_question", "")).strip()),
        "sql_knowledge": bool(sql_knowledge_text),
        "sql_rewrite": bool(sql_rewrite_text),
        "recalled_tables": bool(match.get("recalled_tables")),
        "final_prompt": bool(
            str(match.get("final_prompt", {}).get("combined", "")).strip()
            or str(match.get("final_prompt", {}).get("raw", "")).strip()
        ),
        "generated_ir": bool(str(match.get("generated_ir", "")).strip()),
        "verifier": bool(match.get("verifier_failures")) or str(match.get("flow_status", "unknown")) in {"success", "failed"},
        "end": str(match.get("flow_status", "unknown")) in {"success", "failed"},
    }

    reached = {
        "start": True,
        "ac_enriched_question": direct["ac_enriched_question"] or any(
            direct[key]
            for key in [
                "preprocess_knowledge",
                "preprocess_decision",
                "mask_question",
                "sql_knowledge",
                "sql_rewrite",
                "recalled_tables",
                "final_prompt",
                "generated_ir",
                "verifier",
            ]
        ),
        "preprocess_knowledge": direct["preprocess_knowledge"] or any(
            direct[key]
            for key in [
                "preprocess_decision",
                "mask_question",
                "sql_knowledge",
                "sql_rewrite",
                "recalled_tables",
                "final_prompt",
                "generated_ir",
                "verifier",
            ]
        ),
        "preprocess_decision": direct["preprocess_decision"] or any(
            direct[key]
            for key in [
                "mask_question",
                "sql_knowledge",
                "sql_rewrite",
                "recalled_tables",
                "final_prompt",
                "generated_ir",
                "verifier",
            ]
        ),
        "mask_question": direct["mask_question"] or any(
            direct[key]
            for key in [
                "sql_knowledge",
                "sql_rewrite",
                "recalled_tables",
                "final_prompt",
                "generated_ir",
                "verifier",
            ]
        ),
        "sql_knowledge": direct["sql_knowledge"] or any(
            direct[key]
            for key in [
                "sql_rewrite",
                "recalled_tables",
                "final_prompt",
                "generated_ir",
                "verifier",
            ]
        ),
        "sql_rewrite": direct["sql_rewrite"] or any(
            direct[key]
            for key in [
                "recalled_tables",
                "final_prompt",
                "generated_ir",
                "verifier",
            ]
        ),
        "recalled_tables": direct["recalled_tables"] or any(
            direct[key]
            for key in [
                "final_prompt",
                "generated_ir",
                "verifier",
            ]
        ),
        "final_prompt": direct["final_prompt"] or direct["generated_ir"] or direct["verifier"],
        "generated_ir": direct["generated_ir"] or direct["verifier"] or direct["end"],
        "verifier": direct["verifier"] or (direct["end"] and direct["generated_ir"]),
        "end": direct["end"],
    }

    details = {
        "start": _format_extract_question_tooltip(match),
        "ac_enriched_question": str(match.get("ac_enriched_question", "")).strip(),
        "preprocess_knowledge": preprocess_knowledge_text,
        "preprocess_decision": _format_preprocess_decision_tooltip(match),
        "mask_question": str(match.get("mask_question", "")).strip(),
        "sql_knowledge": sql_knowledge_text,
        "sql_rewrite": sql_rewrite_text,
        "recalled_tables": _format_list_tooltip(match.get("recalled_tables", [])),
        "final_prompt": str(match.get("final_prompt", {}).get("combined", "")).strip() or str(match.get("final_prompt", {}).get("raw", "")).strip(),
        "generated_ir": str(match.get("generated_ir", "")).strip(),
        "verifier": verifier_text,
        "end": end_text,
    }

    flow_status = str(match.get("flow_status", "unknown"))
    preprocess_decision = str(match.get("preprocess_decision", "")).strip()
    nodes: list[dict[str, str]] = []
    for spec in FLOW_NODE_SPECS:
        key = spec["key"]
        status = "complete" if reached.get(key) else "unknown"
        if key == "preprocess_decision":
            if preprocess_decision == "reject_request":
                status = "reject"
            elif preprocess_decision == "ask_human":
                status = "follow-up"
        elif key == "verifier" and flow_status == "failed" and match.get("verifier_failures"):
            status = "failed"
        elif key == "end":
            if flow_status == "success":
                status = "success"
            elif flow_status == "failed":
                status = "failed"
            elif flow_status == "reject":
                status = "reject"
            elif flow_status == "follow_up":
                status = "follow-up"
            else:
                status = "unknown"

        detail = details.get(key, "").strip()
        if not detail:
            detail = "已到达，未提取到详情" if reached.get(key) else "未命中该步骤"

        nodes.append(
            {
                "key": key,
                "label": spec["label"],
                "meta": spec["meta"],
                "index": spec["label"].split(" ", 1)[0] if " " in spec["label"] else spec["label"],
                "status": status,
                "type": str(spec["type"]),
                "detail": detail,
            }
        )
    return nodes


def _format_extract_question_tooltip(match: dict[str, Any]) -> str:
    parts = [
        f"问题: {str(match.get('question', '')).strip()}",
        f"时间: {str(match.get('anchor_timestamp', '')).strip()}",
        "",
        "锚点日志:",
        str(match.get("anchor_line", "")).strip(),
    ]
    return "\n".join(part for part in parts if part is not None).strip()


def _format_preprocess_knowledge_tooltip(preprocess_knowledge: dict[str, Any]) -> str:
    if not isinstance(preprocess_knowledge, dict):
        return ""
    chunks = []
    rewrite_text = _format_knowledge_bundle(preprocess_knowledge.get("rewrite"))
    if rewrite_text:
        chunks.append(f"问题改写:\n{rewrite_text}")
    reject_values = _format_list_tooltip(preprocess_knowledge.get("reject", []))
    if reject_values:
        chunks.append(f"拒答:\n{reject_values}")
    follow_up_values = _format_list_tooltip(preprocess_knowledge.get("follow_up", []))
    if follow_up_values:
        chunks.append(f"追问:\n{follow_up_values}")
    return "\n\n".join(chunks).strip()


def _format_sql_knowledge_tooltip(sql_knowledge: dict[str, Any]) -> str:
    if not isinstance(sql_knowledge, dict):
        return ""
    chunks = []
    generation_text = _format_knowledge_bundle(sql_knowledge.get("generation"))
    if generation_text:
        chunks.append(f"生成逻辑:\n{generation_text}")
    few_shot_text = _format_knowledge_bundle(sql_knowledge.get("few_shot"))
    if few_shot_text:
        chunks.append(f"Few-shot:\n{few_shot_text}")
    return "\n\n".join(chunks).strip()


def _format_sql_rewrite_tooltip(match: dict[str, Any]) -> str:
    chunks = []
    rewritten_question = str(match.get("sql_rewritten_question", "") or match.get("rewritten_question", "")).strip()
    prompt_json = str(match.get("sql_rewrite_prompt_json", "")).strip()
    if rewritten_question:
        chunks.append(f"改写结果:\n{rewritten_question}")
    if prompt_json:
        chunks.append(f"改写提示词:\n{prompt_json}")
    return "\n\n".join(chunks).strip()


def _format_preprocess_decision_tooltip(match: dict[str, Any]) -> str:
    decision = str(match.get("preprocess_decision", "")).strip()
    decision_label = {
        "data_query": "DataQuery",
        "reject_request": "RejectRequest",
        "ask_human": "AskHuman",
    }.get(decision, decision or "-")
    rewritten_question = str(match.get("preprocess_rewritten_question", "")).strip()
    parts = [f"判定: {decision_label}"]
    if rewritten_question:
        parts.append(f"拒答/追问改写:\n{rewritten_question}")
    if decision in {"reject_request", "ask_human"}:
        parts.append("流程在该节点终止，后续步骤未执行。")
    return "\n\n".join(parts).strip()


def _format_verifier_tooltip(match: dict[str, Any]) -> str:
    retry_count = int(match.get("retry_count", 0) or 0)
    failures = [str(item).strip() for item in match.get("verifier_failures", []) if str(item).strip()]
    parts = [f"重试次数: {retry_count}"]
    if failures:
        parts.append("失败原因:\n" + "\n".join(failures))
    return "\n\n".join(parts).strip()


def _format_end_tooltip(match: dict[str, Any]) -> str:
    flow_status = str(match.get("flow_status", "unknown"))
    if flow_status == "success":
        sql_summary = _extract_sql_summary(match)
        if sql_summary:
            return f"流程状态: 成功\n\nSQL 摘要:\n{sql_summary}"
        return "流程状态: 成功\n\n未提取到 SQL 摘要"
    if flow_status == "failed":
        failures = [str(item).strip() for item in match.get("verifier_failures", []) if str(item).strip()]
        if failures:
            return "流程状态: 失败\n\n校验失败原因:\n" + "\n".join(failures)
        return "流程状态: 失败"
    if flow_status == "reject":
        return "流程状态: 拒答\n\n流程在拒答/追问阶段终止。"
    if flow_status == "follow_up":
        return "流程状态: 追问\n\n流程在拒答/追问阶段终止。"
    return "流程状态: 未知\n\n未命中结束信号，流程可能中断或服务重启。"


def _extract_sql_summary(match: dict[str, Any]) -> str:
    candidates = [
        str(match.get("complete_ir", "")),
        str(match.get("generated_ir", "")),
    ]
    prefixes = ("SELECT", "WITH", "INSERT", "UPDATE", "DELETE")
    for candidate in candidates:
        for raw_line in candidate.splitlines():
            line = raw_line.strip()
            upper_line = line.upper()
            if line and upper_line.startswith(prefixes):
                return line
    return ""


def _format_list_tooltip(items: Any) -> str:
    if not isinstance(items, list):
        return ""
    values = [str(item).strip() for item in items if str(item).strip()]
    return "\n".join(values)


def _escape_data_attr(value: str) -> str:
    return escape(value, quote=True).replace("\n", "&#10;")


def _render_nav_match_link(anchor_id: str, match: dict[str, Any], question_anchor_id: str) -> str:
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
        f'<a class="nav-match-link" data-parent-question-anchor="{escape(question_anchor_id)}" '
        f'href="#{escape(anchor_id)}">'
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
        f'<span class="status-chip">拒答/追问判定：{escape(preprocess_label)}</span>'
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


def _wrap_config_item(field_key: str, content: str) -> str:
    return f'<div class="config-item" data-field-key="{escape(field_key)}">{content}</div>'


def _render_placeholder(skipped: bool = False) -> str:
    if skipped:
        return '<div class="missing">未执行（流程在拒答/追问阶段终止）</div>'
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
