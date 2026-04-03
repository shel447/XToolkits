from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from . import __version__

import re

TIMESTAMP_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})")
REQUEST_ID_RE = re.compile(r"(?<!\d)(?P<request_id>\d{15})(?!\d)")

ANCHOR_KEYWORD = "sql_template_match"
QUERY_MARKER = "query:"
RAG_KEYWORD = "knowledge retriever success"
REWRITE_KEYWORD = "rewrite question from"
SCHEMA_KEYWORD = "Schema链接完成"
RECALL_KEYWORD = "召回表"
IR_DEF_START = "表定义的IR"
IR_DEF_STOP = "code guardrail check result"
PROMPT_KEYWORD = "生成器任务"
IR_RESULT_START = "推理结果"
IR_RESULT_STOP = "return result"


def read_log_text(log_path: str | Path, encoding: str | None = None) -> str:
    path = Path(log_path)
    candidates = [encoding] if encoding else ["utf-8", "utf-8-sig", "gbk", "gb18030"]
    last_error: UnicodeDecodeError | None = None
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            return path.read_text(encoding=candidate)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return path.read_text()


def extract_report(
    log_text: str,
    source_log: str,
    question_filter: str | None = None,
) -> dict[str, Any]:
    lines = log_text.splitlines()
    anchors = _collect_anchor_entries(lines)
    selected_questions = _select_questions(anchors, question_filter)
    question_groups = [
        _build_question_group(question=question, anchors=anchors, lines=lines)
        for question in selected_questions
    ]
    report = {
        "tool": "chatbi-smart-query-log-extractor",
        "version": __version__,
        "source_log": source_log,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_questions": len(question_groups),
        "questions": question_groups,
    }
    return report


def has_partial_failures(report: dict[str, Any]) -> bool:
    return any(
        match["missing_sections"] or match["parse_errors"]
        for question_group in report["questions"]
        for match in question_group["matches"]
    )


def _collect_anchor_entries(lines: list[str]) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if ANCHOR_KEYWORD not in line:
            continue
        anchor_question = _extract_anchor_question(line)
        if not anchor_question:
            continue
        request_id = _extract_request_id(line)
        if request_id is None:
            continue
        anchors.append(
            {
                "question": anchor_question,
                "request_id": request_id,
                "anchor_timestamp": _extract_timestamp(line) or "",
                "anchor_line": line,
                "line_number": line_number,
            }
        )
    return anchors


def _select_questions(anchors: list[dict[str, Any]], question_filter: str | None) -> list[str]:
    normalized_filter = question_filter.strip() if question_filter is not None else None
    seen: set[str] = set()
    questions: list[str] = []
    for anchor in anchors:
        question = anchor["question"].strip()
        if normalized_filter is not None and question != normalized_filter:
            continue
        if question in seen:
            continue
        seen.add(question)
        questions.append(question)
    return questions


def _build_question_group(question: str, anchors: list[dict[str, Any]], lines: list[str]) -> dict[str, Any]:
    matching_anchors = [anchor for anchor in anchors if anchor["question"] == question]
    matches = [
        _build_match(index + 1, anchor, lines)
        for index, anchor in enumerate(matching_anchors)
    ]
    return {
        "question": question,
        "total_matches": len(matches),
        "matches": matches,
    }


def _build_match(index: int, anchor: dict[str, Any], lines: list[str]) -> dict[str, Any]:
    request_id = anchor["request_id"]
    rag_results = [
        line.strip() for line in lines if request_id in line and RAG_KEYWORD in line
    ]

    rewritten_question = ""
    for line in lines:
        if request_id in line and REWRITE_KEYWORD in line:
            rewritten_question = _extract_after_last_bracket(line)

    recalled_tables: list[str] = []
    for line in lines:
        if request_id not in line:
            continue
        if RECALL_KEYWORD in line:
            recalled_tables.append(line.split("召回表:", 1)[-1].strip())
        elif SCHEMA_KEYWORD in line:
            recalled_tables.append(line.strip())

    ir_table_definition, ir_def_errors = _extract_multiline_block(
        lines,
        request_id=request_id,
        start_keyword=IR_DEF_START,
        stop_keyword=IR_DEF_STOP,
        include_stop=False,
    )
    generated_ir, generated_ir_errors = _extract_multiline_block(
        lines,
        request_id=request_id,
        start_keyword=IR_RESULT_START,
        stop_keyword=IR_RESULT_STOP,
        include_stop=True,
        include_start=False,
    )
    final_prompt, final_prompt_errors = _extract_final_prompt(lines, request_id)

    missing_sections: list[str] = []
    if not rag_results:
        missing_sections.append("rag_results")
    if not rewritten_question:
        missing_sections.append("rewritten_question")
    if not recalled_tables:
        missing_sections.append("recalled_tables")
    if not ir_table_definition:
        missing_sections.append("ir_table_definition")
    if not final_prompt["raw"] and not final_prompt["combined"]:
        missing_sections.append("final_prompt")
    if not generated_ir:
        missing_sections.append("generated_ir")

    parse_errors = [*ir_def_errors, *final_prompt_errors, *generated_ir_errors]

    return {
        "index": index,
        "request_id": request_id,
        "anchor_timestamp": anchor["anchor_timestamp"],
        "anchor_line": anchor["anchor_line"],
        "line_number": anchor["line_number"],
        "rag_results": rag_results,
        "rewritten_question": rewritten_question,
        "recalled_tables": recalled_tables,
        "ir_table_definition": ir_table_definition,
        "final_prompt": final_prompt,
        "generated_ir": generated_ir,
        "missing_sections": missing_sections,
        "parse_errors": parse_errors,
    }


def _extract_multiline_block(
    lines: list[str],
    request_id: str,
    start_keyword: str,
    stop_keyword: str,
    include_stop: bool,
    include_start: bool = True,
) -> tuple[str, list[str]]:
    start_index: int | None = None
    for index, line in enumerate(lines):
        if request_id in line and start_keyword in line:
            start_index = index
            break

    if start_index is None:
        return "", []

    block_lines: list[str] = []
    stop_found = False
    for index in range(start_index, len(lines)):
        line = lines[index]
        if index == start_index:
            if include_start:
                block_lines.append(line)
            continue
        if stop_keyword in line:
            if include_stop:
                block_lines.append(line)
            stop_found = True
            break
        block_lines.append(line)

    errors: list[str] = []
    if not stop_found:
        errors.append(f"{_section_name_from_keyword(start_keyword)}: missing terminator '{stop_keyword}'")
    return "\n".join(block_lines).strip(), errors


def _extract_final_prompt(lines: list[str], request_id: str) -> tuple[dict[str, str], list[str]]:
    raw_payload = ""
    for line in lines:
        if request_id in line and PROMPT_KEYWORD in line:
            raw_payload = _extract_after_prompt_keyword(line)

    prompt = {"raw": raw_payload, "system": "", "user": "", "combined": ""}
    if not raw_payload:
        return prompt, []

    errors: list[str] = []
    try:
        payload = json.loads(raw_payload)
        if isinstance(payload, str):
            payload = json.loads(payload)
        messages = payload.get("messages") if isinstance(payload, dict) else None
        if not isinstance(messages, list) or len(messages) < 2:
            raise ValueError("messages field missing or incomplete")
        system = _normalize_prompt_content(messages[0].get("content", ""))
        user = _normalize_prompt_content(messages[1].get("content", ""))
        prompt["system"] = system
        prompt["user"] = user
        prompt["combined"] = "\n\n".join(part for part in [system, user] if part)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        errors.append(f"final_prompt: failed to parse payload ({exc})")
    return prompt, errors


def _normalize_prompt_content(value: Any) -> str:
    if not isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    normalized = value
    normalized = normalized.replace("\\r\\n", "\n").replace("\\n", "\n")
    normalized = normalized.replace("\\t", "\t")
    normalized = normalized.replace('\\"', '"')
    normalized = normalized.replace("\\'", "'")
    return normalized


def _extract_after_prompt_keyword(line: str) -> str:
    for marker in ("生成器任务：", "生成器任务:"):
        if marker in line:
            return line.split(marker, 1)[1].strip()
    return line.strip()


def _extract_after_last_bracket(line: str) -> str:
    closing_index = line.rfind("]")
    if closing_index == -1:
        return line.strip()
    return line[closing_index + 1 :].strip()


def _extract_request_id(line: str) -> str | None:
    match = REQUEST_ID_RE.search(line)
    return match.group("request_id") if match else None


def _extract_anchor_question(line: str) -> str | None:
    marker_index = line.find(QUERY_MARKER)
    if marker_index == -1:
        return None
    return line[marker_index + len(QUERY_MARKER) :].strip()


def _extract_timestamp(line: str) -> str | None:
    match = TIMESTAMP_RE.match(line)
    return match.group("ts") if match else None


def _section_name_from_keyword(keyword: str) -> str:
    if keyword == IR_DEF_START:
        return "ir_table_definition"
    if keyword == IR_RESULT_START:
        return "generated_ir"
    return keyword
