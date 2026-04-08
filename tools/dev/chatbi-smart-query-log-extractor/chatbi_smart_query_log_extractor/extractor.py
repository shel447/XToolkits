from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from . import __version__

import re

TIMESTAMP_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})")
THREAD_ID_RE = re.compile(r"(?<!\d)(?P<thread_id>\d{15})(?!\d)")

ANCHOR_KEYWORD = "sql_template_match"
QUERY_MARKER = "query:"
RAG_KEYWORD = "knowledge retriever success"
REWRITE_KEYWORD = "rewrite question from"
SCHEMA_KEYWORD = "Schema链接完成"
RECALL_KEYWORD = "召回表"
IR_DEF_START = "表定义的IR："
IR_DEF_STOP = "code guardrail check result"
PROMPT_KEYWORD = "生成器任务："
IR_RESULT_START = "最终的IR"
IR_RESULT_STOP = "tables = get_tables_columns(table_exprs)"
CALL_SQLFLOW_INPUT_KEYWORD = "call sqlflow input:"
MASK_QUESTION_KEYWORD = "MASK QUESTION:"
VERIFIER_FAIL_KEYWORD = "verifier result: 0:"
FLOW_FAIL_KEYWORD = "sql_flow exception: SQL is empty"
FLOW_SUCCESS_KEYWORD = "sqlflow res: sql:"
AC_QUESTION_KEYWORD = "question after ac: "
PREPROCESS_DECISION_KEYWORD = "react chat llm chient res"
QUERY_INTENT_RE = re.compile(r"""['"]query_intent['"]\s*:\s*['"](?P<query>.*?)['"]""")
KNOWLEDGE_REQUEST_KEYWORD = "knowledge retriever:"
INTENTION_REWRITE_SCOPE = "IntentionRewrite"
SQL_GENERATION_SCOPE = "SQLGeneration"
FEW_SHOT_SCOPE = "SQLGenFewShot"
REJECT_KNOWLEDGE_KEYWORD = "load klg for KlgScope.INTENTION_REJECT: "
FOLLOW_UP_KNOWLEDGE_KEYWORD = "load klg for KlgScope.INTENTION_FOLLOW_UP: "
SQL_REWRITE_PROMPT_KEYWORD = "问题改写任务："

DATA_QUERY_DECISION = "data_query"
REJECT_REQUEST_DECISION = "reject_request"
ASK_HUMAN_DECISION = "ask_human"

SUCCESS_STATUS = "success"
FAILED_STATUS = "failed"
UNKNOWN_STATUS = "unknown"
REJECT_STATUS = "reject"
FOLLOW_UP_STATUS = "follow_up"


def read_log_text(log_path: str | Path, encoding: str | None = None) -> str:
    path = Path(log_path)
    return decode_log_bytes(path.read_bytes(), encoding=encoding)


def decode_log_bytes(raw: bytes, encoding: str | None = None) -> str:
    candidates = [encoding] if encoding else ["utf-8", "utf-8-sig", "gbk", "gb18030"]
    last_error: UnicodeDecodeError | None = None
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            return raw.decode(candidate)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return raw.decode()


def extract_report(
    log_text: str,
    source_log: str,
    question_filter: str | None = None,
) -> dict[str, Any]:
    lines = log_text.splitlines()
    anchors = _collect_anchor_entries(lines)
    cross_thread_matches = _collect_cross_thread_matches(lines)
    cross_thread_match_ids = {match["match_id"] for match in cross_thread_matches}
    fallback_matches = [
        _build_match(0, anchor, lines)
        for anchor in anchors
        if anchor["match_id"] not in cross_thread_match_ids
        and not any(_anchor_is_covered_by_cross_thread_match(anchor, match) for match in cross_thread_matches)
    ]
    all_matches = [*cross_thread_matches, *fallback_matches]
    all_matches.sort(key=lambda match: (int(match.get("line_number", 0)), str(match.get("thread_id", ""))))
    selected_questions = _select_match_questions(all_matches, question_filter)
    question_groups = [
        _build_question_group_from_matches(question=question, matches=all_matches)
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


def _collect_cross_thread_matches(lines: list[str]) -> list[dict[str, Any]]:
    last_anchor_by_thread: dict[str, dict[str, Any]] = {}
    thread_to_match_id: dict[str, str] = {}
    raw_matches_by_id: dict[str, dict[str, Any]] = {}
    ordered_match_ids: list[str] = []
    file_end_line_number = len(lines) + 1

    for line_number, line in enumerate(lines, start=1):
        thread_id = _extract_thread_id(line)
        if thread_id is None:
            continue

        if ANCHOR_KEYWORD in line:
            anchor_question = _extract_anchor_question(line)
            if anchor_question:
                last_anchor_by_thread[thread_id] = {
                    "question": anchor_question,
                    "anchor_timestamp": _extract_timestamp(line) or "",
                    "anchor_line": line,
                    "line_number": line_number,
                }

        if MASK_QUESTION_KEYWORD in line:
            existing_match_id = thread_to_match_id.get(thread_id)
            match_id = _find_open_match_by_mask_question_line(
                ordered_match_ids,
                raw_matches_by_id,
                line,
            )
            if match_id is not None and match_id != existing_match_id:
                if existing_match_id is not None:
                    current_raw_match = raw_matches_by_id.get(existing_match_id)
                    if current_raw_match is not None:
                        _close_match_thread_segment(current_raw_match, thread_id, line_number)
                        if thread_to_match_id.get(thread_id) == existing_match_id:
                            thread_to_match_id.pop(thread_id, None)
                        _finalize_match_if_inactive(
                            current_raw_match,
                            line_number,
                            thread_to_match_id,
                        )
                raw_match = raw_matches_by_id[match_id]
                if raw_match["thread_id"] != thread_id:
                    _associate_thread_to_match(raw_match, thread_id, line_number)
                    thread_to_match_id[thread_id] = match_id

        if CALL_SQLFLOW_INPUT_KEYWORD not in line:
            continue

        rewrite_question = _extract_after_keyword(line, CALL_SQLFLOW_INPUT_KEYWORD)
        current_match_id = thread_to_match_id.get(thread_id)
        if current_match_id is None:
            anchor = _resolve_root_anchor(
                last_anchor_by_thread.get(thread_id),
                fallback_line=line,
                fallback_line_number=line_number,
                fallback_question=rewrite_question,
            )
            raw_match = _open_root_match(
                thread_id=thread_id,
                question=anchor["question"],
                anchor_line=anchor["anchor_line"],
                anchor_timestamp=anchor["anchor_timestamp"],
                anchor_line_number=anchor["line_number"],
                rewrite_question=rewrite_question,
            )
            raw_matches_by_id[raw_match["match_id"]] = raw_match
            ordered_match_ids.append(raw_match["match_id"])
            thread_to_match_id[thread_id] = raw_match["match_id"]
            continue

        current_match = raw_matches_by_id[current_match_id]
        if current_match["thread_id"] == thread_id:
            next_anchor = _resolve_root_anchor(
                last_anchor_by_thread.get(thread_id),
                fallback_line=line,
                fallback_line_number=line_number,
                fallback_question=rewrite_question,
            )
            next_call_start_line_number = (
                next_anchor["line_number"]
                if next_anchor["line_number"] > current_match["line_number"]
                else line_number
            )
            _close_match_thread_segment(current_match, thread_id, next_call_start_line_number)
            if thread_to_match_id.get(thread_id) == current_match_id:
                thread_to_match_id.pop(thread_id, None)
            _finalize_match_if_inactive(
                current_match,
                next_call_start_line_number,
                thread_to_match_id,
            )
            raw_match = _open_root_match(
                thread_id=thread_id,
                question=next_anchor["question"],
                anchor_line=next_anchor["anchor_line"],
                anchor_timestamp=next_anchor["anchor_timestamp"],
                anchor_line_number=next_anchor["line_number"],
                rewrite_question=rewrite_question,
            )
            raw_matches_by_id[raw_match["match_id"]] = raw_match
            ordered_match_ids.append(raw_match["match_id"])
            thread_to_match_id[thread_id] = raw_match["match_id"]
            continue

        if rewrite_question and rewrite_question not in current_match["rewrite_questions"]:
            current_match["rewrite_questions"].append(rewrite_question)

    for match_id in ordered_match_ids:
        raw_match = raw_matches_by_id[match_id]
        if raw_match["end_line_number"] is None:
            _close_raw_match(raw_match, file_end_line_number, thread_to_match_id)

    return [
        _build_cross_thread_match(index + 1, raw_matches_by_id[match_id], lines)
        for index, match_id in enumerate(ordered_match_ids)
    ]


def _open_root_match(
    thread_id: str,
    question: str,
    anchor_line: str,
    anchor_timestamp: str,
    anchor_line_number: int,
    rewrite_question: str,
) -> dict[str, Any]:
    return {
        "question": question,
        "thread_id": thread_id,
        "match_id": _build_match_id(thread_id, anchor_line_number),
        "anchor_timestamp": anchor_timestamp,
        "anchor_line": anchor_line,
        "line_number": anchor_line_number,
        "associated_thread_ids": [],
        "rewrite_questions": [rewrite_question] if rewrite_question else [],
        "segments": {thread_id: [{"start_line_number": anchor_line_number, "end_line_number": None}]},
        "participant_thread_ids": [thread_id],
        "end_line_number": None,
    }


def _resolve_root_anchor(
    anchor: dict[str, Any] | None,
    fallback_line: str,
    fallback_line_number: int,
    fallback_question: str,
) -> dict[str, Any]:
    if anchor is not None:
        return {
            "question": str(anchor.get("question", "")).strip() or fallback_question,
            "anchor_timestamp": str(anchor.get("anchor_timestamp", "")),
            "anchor_line": str(anchor.get("anchor_line", fallback_line)),
            "line_number": int(anchor.get("line_number", fallback_line_number)),
        }
    return {
        "question": fallback_question,
        "anchor_timestamp": _extract_timestamp(fallback_line) or "",
        "anchor_line": fallback_line,
        "line_number": fallback_line_number,
    }


def _close_raw_match(
    raw_match: dict[str, Any],
    end_line_number: int,
    thread_to_match_id: dict[str, str],
) -> None:
    raw_match["end_line_number"] = end_line_number
    for thread_id, segments in raw_match["segments"].items():
        if segments and segments[-1]["end_line_number"] is None:
            segments[-1]["end_line_number"] = end_line_number
        if thread_to_match_id.get(thread_id) == raw_match["match_id"]:
            thread_to_match_id.pop(thread_id, None)


def _close_match_thread_segment(raw_match: dict[str, Any], thread_id: str, end_line_number: int) -> None:
    segments = raw_match["segments"].get(thread_id) or []
    if not segments:
        return
    if segments[-1]["end_line_number"] is None:
        segments[-1]["end_line_number"] = end_line_number


def _finalize_match_if_inactive(
    raw_match: dict[str, Any],
    end_line_number: int,
    thread_to_match_id: dict[str, str],
) -> None:
    match_id = raw_match["match_id"]
    if any(active_match_id == match_id for active_match_id in thread_to_match_id.values()):
        return
    if raw_match["end_line_number"] is None:
        raw_match["end_line_number"] = end_line_number


def _associate_thread_to_match(raw_match: dict[str, Any], thread_id: str, line_number: int) -> None:
    if thread_id not in raw_match["associated_thread_ids"]:
        raw_match["associated_thread_ids"].append(thread_id)
    if thread_id not in raw_match["participant_thread_ids"]:
        raw_match["participant_thread_ids"].append(thread_id)
    raw_match["segments"].setdefault(thread_id, []).append(
        {"start_line_number": line_number, "end_line_number": None}
    )


def _find_open_match_by_mask_question_line(
    ordered_match_ids: list[str],
    raw_matches_by_id: dict[str, dict[str, Any]],
    line: str,
) -> str | None:
    for match_id in reversed(ordered_match_ids):
        raw_match = raw_matches_by_id[match_id]
        if raw_match["end_line_number"] is not None:
            continue
        for rewrite_question in raw_match["rewrite_questions"]:
            if _build_mask_question_marker(rewrite_question) in line:
                return match_id
    return None


def _build_mask_question_marker(question: str) -> str:
    return f"{MASK_QUESTION_KEYWORD} {question}".strip()


def _select_match_questions(matches: list[dict[str, Any]], question_filter: str | None) -> list[str]:
    normalized_filter = question_filter.strip() if question_filter is not None else None
    seen: set[str] = set()
    questions: list[str] = []
    for match in matches:
        question = str(match["question"]).strip()
        if normalized_filter is not None and question != normalized_filter:
            continue
        if question in seen:
            continue
        seen.add(question)
        questions.append(question)
    return questions


def _build_question_group_from_matches(question: str, matches: list[dict[str, Any]]) -> dict[str, Any]:
    grouped_matches = [match for match in matches if match["question"] == question]
    normalized_matches = []
    for index, match in enumerate(grouped_matches, start=1):
        normalized_match = {key: value for key, value in match.items() if not key.startswith("_")}
        normalized_match["index"] = index
        normalized_matches.append(normalized_match)
    return {
        "question": question,
        "total_matches": len(normalized_matches),
        "matches": normalized_matches,
    }


def _collect_anchor_entries(lines: list[str]) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    file_end_line_number = len(lines) + 1
    last_anchor_index_by_thread: dict[str, int] = {}
    for line_number, line in enumerate(lines, start=1):
        if ANCHOR_KEYWORD not in line:
            continue
        anchor_question = _extract_anchor_question(line)
        if not anchor_question:
            continue
        thread_id = _extract_thread_id(line)
        if thread_id is None:
            continue
        previous_anchor_index = last_anchor_index_by_thread.get(thread_id)
        if previous_anchor_index is not None:
            anchors[previous_anchor_index]["window_end_line_number"] = line_number
        anchors.append(
            {
                "question": anchor_question,
                "thread_id": thread_id,
                "match_id": _build_match_id(thread_id, line_number),
                "anchor_timestamp": _extract_timestamp(line) or "",
                "anchor_line": line,
                "line_number": line_number,
                "window_end_line_number": file_end_line_number,
            }
        )
        last_anchor_index_by_thread[thread_id] = len(anchors) - 1
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


def _build_window_log_entries(lines: list[str], thread_id: str, start_line_number: int) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for offset, line in enumerate(lines):
        if not _line_has_thread_id(line, thread_id):
            continue
        entries.append(
            {
                "line_number": start_line_number + offset,
                "thread_id": thread_id,
                "line": line,
            }
        )
    return entries


def _anchor_is_covered_by_cross_thread_match(anchor: dict[str, Any], match: dict[str, Any]) -> bool:
    segments = match.get("_segments", {})
    thread_segments = segments.get(anchor["thread_id"], [])
    for segment in thread_segments:
        start_line_number = int(segment.get("start_line_number", 0))
        end_line_number = int(segment.get("end_line_number") or 0)
        if start_line_number <= int(anchor["line_number"]) < end_line_number:
            return True
    return False


def _default_knowledge_bundle(scope: str) -> dict[str, str]:
    return {
        "scope": scope,
        "global_result": "",
        "scope_result": "",
    }


def _extract_line_value(entries: list[dict[str, Any]], keyword: str) -> str:
    value = ""
    for entry in entries:
        line = entry["line"]
        if keyword in line:
            value = _extract_after_keyword(line, keyword)
    return value


def _extract_last_mask_question(entries: list[dict[str, Any]]) -> str:
    return _extract_line_value(entries, MASK_QUESTION_KEYWORD)


def _extract_preprocess_decision(entries: list[dict[str, Any]]) -> dict[str, Any]:
    decision = ""
    raw_line = ""
    rewritten_question = ""
    for entry in entries:
        line = entry["line"]
        if PREPROCESS_DECISION_KEYWORD not in line:
            continue
        raw_line = line
        if "RejectRequest" in line:
            decision = REJECT_REQUEST_DECISION
        elif "AskHuman" in line:
            decision = ASK_HUMAN_DECISION
        elif "DataQuery" in line:
            decision = DATA_QUERY_DECISION
        payload_text = _extract_after_keyword(line, PREPROCESS_DECISION_KEYWORD)
        if payload_text:
            try:
                payload = _load_prompt_payload(payload_text)
            except (json.JSONDecodeError, ValueError, TypeError, SyntaxError):
                payload = None
            if isinstance(payload, dict):
                payload_type = str(payload.get("type", "")).strip()
                if payload_type == "RejectRequest":
                    decision = REJECT_REQUEST_DECISION
                elif payload_type == "AskHuman":
                    decision = ASK_HUMAN_DECISION
                elif payload_type == "DataQuery":
                    decision = DATA_QUERY_DECISION
                payload_intent = payload.get("query_intent")
                if isinstance(payload_intent, str) and payload_intent.strip():
                    rewritten_question = payload_intent.strip()
        if not rewritten_question:
            query_match = QUERY_INTENT_RE.search(line)
            if query_match:
                rewritten_question = query_match.group("query").strip()
    return {
        "decision": decision,
        "raw_line": raw_line,
        "rewritten_question": rewritten_question,
    }


def _extract_last_knowledge_sequence(entries: list[dict[str, Any]], scope_keyword: str) -> dict[str, str]:
    bundle = _default_knowledge_bundle(scope_keyword)
    thread_entries: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        thread_entries.setdefault(entry["thread_id"], []).append(entry)

    best_candidate: tuple[int, dict[str, str]] | None = None
    for scoped_entries in thread_entries.values():
        scoped_entries.sort(key=lambda item: item["line_number"])
        current = _default_knowledge_bundle(scope_keyword)
        pending_request_scope = ""
        for entry in scoped_entries:
            line = entry["line"]
            if KNOWLEDGE_REQUEST_KEYWORD in line:
                if "Global" in line:
                    pending_request_scope = "global"
                elif scope_keyword in line:
                    pending_request_scope = "scope"
                else:
                    pending_request_scope = ""
                continue
            if pending_request_scope and RAG_KEYWORD in line:
                result = _extract_after_keyword(line, RAG_KEYWORD)
                if pending_request_scope == "global":
                    current["global_result"] = result
                elif pending_request_scope == "scope":
                    current["scope_result"] = result
                    if result:
                        best_candidate = (
                            entry["line_number"],
                            {
                                "scope": scope_keyword,
                                "global_result": current["global_result"],
                                "scope_result": current["scope_result"],
                            },
                        )
                pending_request_scope = ""
    return best_candidate[1] if best_candidate is not None else bundle


def _extract_matching_lines(entries: list[dict[str, Any]], keyword: str) -> list[str]:
    results: list[str] = []
    for entry in entries:
        line = entry["line"]
        if keyword in line:
            value = _extract_after_keyword(line, keyword)
            if value:
                results.append(value)
    return results


def _extract_sql_rewrite(entries: list[dict[str, Any]]) -> tuple[str, str, str, list[str]]:
    raw_prompt = ""
    rewritten_question = ""
    errors: list[str] = []

    for entry in entries:
        line = entry["line"]
        if SQL_REWRITE_PROMPT_KEYWORD in line:
            raw_prompt = _extract_after_keyword(line, SQL_REWRITE_PROMPT_KEYWORD)
        if REWRITE_KEYWORD in line:
            rewritten_question = _extract_sql_rewritten_question(line)

    prompt_json = ""
    if raw_prompt:
        try:
            payload = _load_prompt_payload(raw_prompt)
            prompt_json = json.dumps(payload, ensure_ascii=False, indent=2)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            errors.append(f"sql_rewrite_prompt: failed to parse payload ({exc})")

    return raw_prompt, prompt_json, rewritten_question, errors


def _extract_sql_rewritten_question(line: str) -> str:
    content = _extract_after_keyword(line, REWRITE_KEYWORD)
    if " to " in content:
        return content.split(" to ", 1)[1].strip()
    return _extract_after_last_bracket(line)


def _resolve_flow_status(
    has_failed: bool,
    has_succeeded: bool,
    preprocess_decision: str,
) -> str:
    if has_failed:
        return FAILED_STATUS
    if has_succeeded:
        return SUCCESS_STATUS
    if preprocess_decision == REJECT_REQUEST_DECISION:
        return REJECT_STATUS
    if preprocess_decision == ASK_HUMAN_DECISION:
        return FOLLOW_UP_STATUS
    return UNKNOWN_STATUS


def _build_skipped_sections(terminated_at_preprocess: bool) -> list[str]:
    if not terminated_at_preprocess:
        return []
    return [
        "mask_question",
        "sql_generation_knowledge",
        "few_shot_knowledge",
        "sql_knowledge",
        "sql_rewrite_prompt",
        "sql_rewritten_question",
        "recalled_tables",
        "ir_table_definition",
        "final_prompt",
        "generated_ir",
        "complete_ir",
    ]


def _is_skipped(skipped_sections: list[str], section_name: str) -> bool:
    return section_name in skipped_sections


def _build_match(index: int, anchor: dict[str, Any], lines: list[str]) -> dict[str, Any]:
    thread_id = anchor["thread_id"]
    match_id = anchor["match_id"]
    window_lines = lines[anchor["line_number"] - 1 : anchor["window_end_line_number"] - 1]
    log_entries = _build_window_log_entries(window_lines, thread_id, anchor["line_number"])
    preprocess_entries = list(log_entries)

    preprocess_info = _extract_preprocess_decision(preprocess_entries)
    preprocess_decision = preprocess_info["decision"]
    terminated_at_preprocess = preprocess_decision in {REJECT_REQUEST_DECISION, ASK_HUMAN_DECISION}
    skipped_sections = _build_skipped_sections(terminated_at_preprocess)
    ac_enriched_question = _extract_line_value(preprocess_entries, AC_QUESTION_KEYWORD)
    preprocess_knowledge = {
        "rewrite": _extract_last_knowledge_sequence(preprocess_entries, INTENTION_REWRITE_SCOPE),
        "reject": _extract_matching_lines(preprocess_entries, REJECT_KNOWLEDGE_KEYWORD),
        "follow_up": _extract_matching_lines(preprocess_entries, FOLLOW_UP_KNOWLEDGE_KEYWORD),
    }

    verifier_failures = [
        _extract_after_keyword(entry["line"], VERIFIER_FAIL_KEYWORD)
        for entry in log_entries
        if VERIFIER_FAIL_KEYWORD in entry["line"]
    ]
    has_failed = any(FLOW_FAIL_KEYWORD in entry["line"] for entry in log_entries)
    has_succeeded = any(FLOW_SUCCESS_KEYWORD in entry["line"] for entry in log_entries)
    flow_status = _resolve_flow_status(has_failed, has_succeeded, preprocess_decision)
    rag_results = [
        entry["line"].strip()
        for entry in log_entries
        if RAG_KEYWORD in entry["line"]
    ]

    recalled_tables: list[str] = []
    for entry in log_entries:
        line = entry["line"]
        if RECALL_KEYWORD in line:
            recalled_tables.append(line.split("召回表:", 1)[-1].strip())
        elif SCHEMA_KEYWORD in line:
            recalled_tables.append(line.strip())

    ir_table_definition, ir_def_errors = _extract_multiline_block(
        window_lines,
        thread_id=thread_id,
        start_keyword=IR_DEF_START,
        stop_keyword=IR_DEF_STOP,
        include_stop=False,
        start_mode="after_keyword",
    )
    generated_ir, generated_ir_errors = _extract_multiline_block(
        window_lines,
        thread_id=thread_id,
        start_keyword=IR_RESULT_START,
        stop_keyword=IR_RESULT_STOP,
        include_stop=True,
        start_mode="after_keyword",
    )
    final_prompt, final_prompt_errors = _extract_final_prompt(window_lines, thread_id)
    complete_ir, complete_ir_errors = _build_complete_ir(
        ir_table_definition,
        generated_ir,
        ir_def_errors=ir_def_errors,
        generated_ir_errors=generated_ir_errors,
    )
    mask_question = "" if terminated_at_preprocess else _extract_last_mask_question(log_entries)
    sql_generation_knowledge = (
        _default_knowledge_bundle(SQL_GENERATION_SCOPE)
        if terminated_at_preprocess
        else _extract_last_knowledge_sequence(log_entries, SQL_GENERATION_SCOPE)
    )
    few_shot_knowledge = (
        _default_knowledge_bundle(FEW_SHOT_SCOPE)
        if terminated_at_preprocess
        else _extract_last_knowledge_sequence(log_entries, FEW_SHOT_SCOPE)
    )
    sql_knowledge = {
        "generation": sql_generation_knowledge,
        "few_shot": few_shot_knowledge,
    }
    sql_rewrite_prompt_raw, sql_rewrite_prompt_json, sql_rewritten_question, sql_rewrite_errors = (
        ("", "", "", [])
        if terminated_at_preprocess
        else _extract_sql_rewrite(log_entries)
    )
    rewritten_question = sql_rewritten_question

    missing_sections: list[str] = []
    if not _is_skipped(skipped_sections, "sql_rewritten_question") and not rewritten_question:
        missing_sections.append("rewritten_question")
    if not _is_skipped(skipped_sections, "recalled_tables") and not recalled_tables:
        missing_sections.append("recalled_tables")
    if not _is_skipped(skipped_sections, "ir_table_definition") and not ir_table_definition:
        missing_sections.append("ir_table_definition")
    if not _is_skipped(skipped_sections, "final_prompt") and not final_prompt["raw"] and not final_prompt["combined"]:
        missing_sections.append("final_prompt")
    if not _is_skipped(skipped_sections, "generated_ir") and not generated_ir:
        missing_sections.append("generated_ir")
    if not _is_skipped(skipped_sections, "complete_ir") and not complete_ir:
        missing_sections.append("complete_ir")

    parse_errors = [
        *ir_def_errors,
        *final_prompt_errors,
        *generated_ir_errors,
        *complete_ir_errors,
        *sql_rewrite_errors,
    ]

    return {
        "index": index,
        "question": anchor["question"],
        "thread_id": thread_id,
        "match_id": match_id,
        "anchor_timestamp": anchor["anchor_timestamp"],
        "anchor_line": anchor["anchor_line"],
        "line_number": anchor["line_number"],
        "associated_thread_ids": [],
        "rewrite_questions": [],
        "ac_enriched_question": ac_enriched_question,
        "preprocess_rewritten_question": preprocess_info["rewritten_question"],
        "preprocess_decision": preprocess_decision,
        "preprocess_knowledge": preprocess_knowledge,
        "mask_question": mask_question,
        "sql_generation_knowledge": sql_generation_knowledge,
        "few_shot_knowledge": few_shot_knowledge,
        "sql_knowledge": sql_knowledge,
        "sql_rewrite_prompt_raw": sql_rewrite_prompt_raw,
        "sql_rewrite_prompt_json": sql_rewrite_prompt_json,
        "rag_results": rag_results,
        "rewritten_question": rewritten_question,
        "sql_rewritten_question": sql_rewritten_question,
        "recalled_tables": recalled_tables,
        "ir_table_definition": ir_table_definition,
        "final_prompt": final_prompt,
        "generated_ir": generated_ir,
        "complete_ir": complete_ir,
        "flow_status": flow_status,
        "terminated_at_preprocess": terminated_at_preprocess,
        "skipped_sections": skipped_sections,
        "retry_count": len(verifier_failures),
        "verifier_failures": verifier_failures,
        "missing_sections": missing_sections,
        "parse_errors": parse_errors,
    }


def _build_cross_thread_match(index: int, raw_match: dict[str, Any], lines: list[str]) -> dict[str, Any]:
    segment_views = _build_segment_views(raw_match, lines)
    log_entries = _collect_segment_log_entries(segment_views)
    root_entries = [entry for entry in log_entries if entry["thread_id"] == raw_match["thread_id"]]
    preprocess_info = _extract_preprocess_decision(root_entries)
    preprocess_decision = preprocess_info["decision"]
    terminated_at_preprocess = preprocess_decision in {REJECT_REQUEST_DECISION, ASK_HUMAN_DECISION}
    skipped_sections = _build_skipped_sections(terminated_at_preprocess)
    ac_enriched_question = _extract_line_value(root_entries, AC_QUESTION_KEYWORD)
    preprocess_knowledge = {
        "rewrite": _extract_last_knowledge_sequence(root_entries, INTENTION_REWRITE_SCOPE),
        "reject": _extract_matching_lines(root_entries, REJECT_KNOWLEDGE_KEYWORD),
        "follow_up": _extract_matching_lines(root_entries, FOLLOW_UP_KNOWLEDGE_KEYWORD),
    }
    verifier_failures = [
        _extract_after_keyword(entry["line"], VERIFIER_FAIL_KEYWORD)
        for entry in log_entries
        if VERIFIER_FAIL_KEYWORD in entry["line"]
    ]
    has_failed = any(FLOW_FAIL_KEYWORD in entry["line"] for entry in log_entries)
    has_succeeded = any(FLOW_SUCCESS_KEYWORD in entry["line"] for entry in log_entries)
    flow_status = _resolve_flow_status(has_failed, has_succeeded, preprocess_decision)
    rag_results = [
        entry["line"].strip()
        for entry in log_entries
        if RAG_KEYWORD in entry["line"]
    ]

    recalled_tables: list[str] = []
    for entry in log_entries:
        line = entry["line"]
        if RECALL_KEYWORD in line:
            recalled_tables.append(line.split("召回表:", 1)[-1].strip())
        elif SCHEMA_KEYWORD in line:
            recalled_tables.append(line.strip())

    ir_table_definition, ir_def_errors = _extract_last_multiline_block_from_segments(
        segment_views,
        start_keyword=IR_DEF_START,
        stop_keyword=IR_DEF_STOP,
        include_stop=False,
        start_mode="after_keyword",
    )
    generated_ir, generated_ir_errors = _extract_last_multiline_block_from_segments(
        segment_views,
        start_keyword=IR_RESULT_START,
        stop_keyword=IR_RESULT_STOP,
        include_stop=True,
        start_mode="after_keyword",
    )
    final_prompt, final_prompt_errors = _extract_final_prompt_from_segments(log_entries)
    complete_ir, complete_ir_errors = _build_complete_ir(
        ir_table_definition,
        generated_ir,
        ir_def_errors=ir_def_errors,
        generated_ir_errors=generated_ir_errors,
    )
    mask_question = "" if terminated_at_preprocess else _extract_last_mask_question(log_entries)
    sql_generation_knowledge = (
        _default_knowledge_bundle(SQL_GENERATION_SCOPE)
        if terminated_at_preprocess
        else _extract_last_knowledge_sequence(log_entries, SQL_GENERATION_SCOPE)
    )
    few_shot_knowledge = (
        _default_knowledge_bundle(FEW_SHOT_SCOPE)
        if terminated_at_preprocess
        else _extract_last_knowledge_sequence(log_entries, FEW_SHOT_SCOPE)
    )
    sql_knowledge = {
        "generation": sql_generation_knowledge,
        "few_shot": few_shot_knowledge,
    }
    sql_rewrite_prompt_raw, sql_rewrite_prompt_json, sql_rewritten_question, sql_rewrite_errors = (
        ("", "", "", [])
        if terminated_at_preprocess
        else _extract_sql_rewrite(log_entries)
    )

    rewritten_question = sql_rewritten_question or (raw_match["rewrite_questions"][0] if raw_match["rewrite_questions"] else "")

    missing_sections: list[str] = []
    if not _is_skipped(skipped_sections, "sql_rewritten_question") and not rewritten_question:
        missing_sections.append("rewritten_question")
    if not _is_skipped(skipped_sections, "recalled_tables") and not recalled_tables:
        missing_sections.append("recalled_tables")
    if not _is_skipped(skipped_sections, "ir_table_definition") and not ir_table_definition:
        missing_sections.append("ir_table_definition")
    if not _is_skipped(skipped_sections, "final_prompt") and not final_prompt["raw"] and not final_prompt["combined"]:
        missing_sections.append("final_prompt")
    if not _is_skipped(skipped_sections, "generated_ir") and not generated_ir:
        missing_sections.append("generated_ir")
    if not _is_skipped(skipped_sections, "complete_ir") and not complete_ir:
        missing_sections.append("complete_ir")

    parse_errors = [
        *ir_def_errors,
        *final_prompt_errors,
        *generated_ir_errors,
        *complete_ir_errors,
        *sql_rewrite_errors,
    ]

    return {
        "index": index,
        "question": raw_match["question"],
        "thread_id": raw_match["thread_id"],
        "match_id": raw_match["match_id"],
        "anchor_timestamp": raw_match["anchor_timestamp"],
        "anchor_line": raw_match["anchor_line"],
        "line_number": raw_match["line_number"],
        "associated_thread_ids": list(raw_match["associated_thread_ids"]),
        "rewrite_questions": list(raw_match["rewrite_questions"]),
        "_segments": raw_match["segments"],
        "ac_enriched_question": ac_enriched_question,
        "preprocess_rewritten_question": preprocess_info["rewritten_question"],
        "preprocess_decision": preprocess_decision,
        "preprocess_knowledge": preprocess_knowledge,
        "mask_question": mask_question,
        "sql_generation_knowledge": sql_generation_knowledge,
        "few_shot_knowledge": few_shot_knowledge,
        "sql_knowledge": sql_knowledge,
        "sql_rewrite_prompt_raw": sql_rewrite_prompt_raw,
        "sql_rewrite_prompt_json": sql_rewrite_prompt_json,
        "rag_results": rag_results,
        "rewritten_question": rewritten_question,
        "sql_rewritten_question": sql_rewritten_question,
        "recalled_tables": recalled_tables,
        "ir_table_definition": ir_table_definition,
        "final_prompt": final_prompt,
        "generated_ir": generated_ir,
        "complete_ir": complete_ir,
        "flow_status": flow_status,
        "terminated_at_preprocess": terminated_at_preprocess,
        "skipped_sections": skipped_sections,
        "retry_count": len(verifier_failures),
        "verifier_failures": verifier_failures,
        "missing_sections": missing_sections,
        "parse_errors": parse_errors,
    }


def _build_segment_views(raw_match: dict[str, Any], lines: list[str]) -> list[dict[str, Any]]:
    segment_views: list[dict[str, Any]] = []
    for thread_id, segments in raw_match["segments"].items():
        for segment in segments:
            start_line_number = segment["start_line_number"]
            end_line_number = segment["end_line_number"] or (len(lines) + 1)
            segment_views.append(
                {
                    "thread_id": thread_id,
                    "start_line_number": start_line_number,
                    "end_line_number": end_line_number,
                    "lines": lines[start_line_number - 1 : end_line_number - 1],
                }
            )
    segment_views.sort(key=lambda item: (item["start_line_number"], item["thread_id"]))
    return segment_views


def _collect_segment_log_entries(segment_views: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for segment_view in segment_views:
        thread_id = segment_view["thread_id"]
        for offset, line in enumerate(segment_view["lines"]):
            line_number = segment_view["start_line_number"] + offset
            if not _line_has_thread_id(line, thread_id):
                continue
            entries.append({"line_number": line_number, "thread_id": thread_id, "line": line})
    entries.sort(key=lambda item: item["line_number"])
    return entries


def _extract_last_multiline_block_from_segments(
    segment_views: list[dict[str, Any]],
    start_keyword: str,
    stop_keyword: str,
    include_stop: bool,
    start_mode: str = "whole_line",
) -> tuple[str, list[str]]:
    candidates: list[dict[str, Any]] = []
    for segment_view in segment_views:
        candidates.extend(
            _extract_multiline_block_candidates(
                lines=segment_view["lines"],
                thread_id=segment_view["thread_id"],
                start_line_number=segment_view["start_line_number"],
                start_keyword=start_keyword,
                stop_keyword=stop_keyword,
                include_stop=include_stop,
                start_mode=start_mode,
            )
        )
    if not candidates:
        return "", []
    candidates.sort(key=lambda item: item["start_line_number"])
    selected = candidates[-1]
    return selected["content"], selected["errors"]


def _extract_multiline_block_candidates(
    lines: list[str],
    thread_id: str,
    start_line_number: int,
    start_keyword: str,
    stop_keyword: str,
    include_stop: bool,
    start_mode: str = "whole_line",
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for start_index, line in enumerate(lines):
        if not (_line_has_thread_id(line, thread_id) and start_keyword in line):
            continue

        block_lines: list[str] = []
        stop_found = False
        for index in range(start_index, len(lines)):
            current_line = lines[index]
            if index == start_index:
                if start_mode == "whole_line":
                    block_lines.append(current_line)
                elif start_mode == "after_keyword":
                    start_content = _extract_after_keyword(current_line, start_keyword)
                    if start_content:
                        block_lines.append(start_content)
                elif start_mode != "skip":
                    raise ValueError(f"unsupported start_mode: {start_mode}")
                continue
            if stop_keyword in current_line:
                if include_stop:
                    block_lines.append(current_line)
                stop_found = True
                break
            if _is_log_line(current_line):
                if _line_has_thread_id(current_line, thread_id):
                    break
                continue
            block_lines.append(current_line)

        errors: list[str] = []
        if not stop_found:
            errors.append(f"{_section_name_from_keyword(start_keyword)}: missing terminator '{stop_keyword}'")
        candidates.append(
            {
                "start_line_number": start_line_number + start_index,
                "content": "\n".join(block_lines).strip(),
                "errors": errors,
            }
        )
    return candidates


def _extract_final_prompt_from_segments(log_entries: list[dict[str, Any]]) -> tuple[dict[str, str], list[str]]:
    raw_payload = ""
    for entry in log_entries:
        if PROMPT_KEYWORD in entry["line"]:
            raw_payload = _extract_after_prompt_keyword(entry["line"])

    prompt = {"raw": raw_payload, "system": "", "user": "", "combined": ""}
    if not raw_payload:
        return prompt, []

    errors: list[str] = []
    try:
        payload = _load_prompt_payload(raw_payload)
        messages = _extract_prompt_messages(payload)
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


def _extract_multiline_block(
    lines: list[str],
    thread_id: str,
    start_keyword: str,
    stop_keyword: str,
    include_stop: bool,
    start_mode: str = "whole_line",
) -> tuple[str, list[str]]:
    start_index: int | None = None
    for index, line in enumerate(lines):
        if _line_has_thread_id(line, thread_id) and start_keyword in line:
            start_index = index
            break

    if start_index is None:
        return "", []

    block_lines: list[str] = []
    stop_found = False
    for index in range(start_index, len(lines)):
        line = lines[index]
        if index == start_index:
            if start_mode == "whole_line":
                block_lines.append(line)
            elif start_mode == "after_keyword":
                start_content = _extract_after_keyword(line, start_keyword)
                if start_content:
                    block_lines.append(start_content)
            elif start_mode != "skip":
                raise ValueError(f"unsupported start_mode: {start_mode}")
            continue
        if stop_keyword in line:
            if include_stop:
                block_lines.append(line)
            stop_found = True
            break
        if _is_log_line(line):
            if _line_has_thread_id(line, thread_id):
                break
            continue
        block_lines.append(line)

    errors: list[str] = []
    if not stop_found:
        errors.append(f"{_section_name_from_keyword(start_keyword)}: missing terminator '{stop_keyword}'")
    return "\n".join(block_lines).strip(), errors


def _extract_final_prompt(lines: list[str], thread_id: str) -> tuple[dict[str, str], list[str]]:
    raw_payload = ""
    for line in lines:
        if _line_has_thread_id(line, thread_id) and PROMPT_KEYWORD in line:
            raw_payload = _extract_after_prompt_keyword(line)

    prompt = {"raw": raw_payload, "system": "", "user": "", "combined": ""}
    if not raw_payload:
        return prompt, []

    errors: list[str] = []
    try:
        payload = _load_prompt_payload(raw_payload)
        messages = _extract_prompt_messages(payload)
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


def _load_prompt_payload(raw_payload: str) -> Any:
    current: Any = raw_payload
    last_error: Exception | None = None
    for _ in range(3):
        if isinstance(current, (dict, list)):
            return current
        if not isinstance(current, str):
            break
        text = current.strip()
        if not text:
            break
        for loader in (json.loads, ast.literal_eval):
            try:
                current = loader(text)
                break
            except (json.JSONDecodeError, SyntaxError, ValueError) as exc:
                last_error = exc
        else:
            break
    if isinstance(current, (dict, list)):
        return current
    if last_error is not None:
        raise ValueError(str(last_error))
    raise ValueError("payload is not a dict/list-like object")


def _extract_prompt_messages(payload: Any) -> list[dict[str, Any]] | None:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return None
    messages = payload.get("messages")
    if isinstance(messages, list):
        return messages
    return None


def _extract_after_prompt_keyword(line: str) -> str:
    return _extract_after_keyword(line, PROMPT_KEYWORD)


def _extract_after_keyword(line: str, keyword: str) -> str:
    if keyword not in line:
        return ""
    remainder = line.split(keyword, 1)[1]
    return remainder.lstrip(" ：:").strip()


def _build_complete_ir(
    ir_table_definition: str,
    generated_ir: str,
    ir_def_errors: list[str],
    generated_ir_errors: list[str],
) -> tuple[str, list[str]]:
    if not ir_table_definition or not generated_ir:
        return "", []
    if ir_def_errors or generated_ir_errors:
        return "", ["complete_ir: source sections incomplete"]

    generated_lines = generated_ir.splitlines()
    anchor_index: int | None = None
    for index, line in enumerate(generated_lines):
        if line.strip() == "@dataclass":
            anchor_index = index
            break

    if anchor_index is None:
        return "", ["complete_ir: missing '@dataclass' insertion anchor"]

    after_anchor = "\n".join(generated_lines[anchor_index:]).strip()
    sections = [section for section in (ir_table_definition.strip(), after_anchor) if section]
    return "\n\n".join(sections).strip(), []


def _extract_after_last_bracket(line: str) -> str:
    closing_index = line.rfind("]")
    if closing_index == -1:
        return line.strip()
    return line[closing_index + 1 :].strip()


def _extract_thread_id(line: str) -> str | None:
    match = THREAD_ID_RE.search(line)
    return match.group("thread_id") if match else None


def _build_match_id(thread_id: str, line_number: int) -> str:
    return f"{thread_id}:{line_number}"


def _extract_anchor_question(line: str) -> str | None:
    marker_index = line.find(QUERY_MARKER)
    if marker_index == -1:
        return None
    return line[marker_index + len(QUERY_MARKER) :].strip()


def _extract_timestamp(line: str) -> str | None:
    match = TIMESTAMP_RE.match(line)
    return match.group("ts") if match else None


def _is_log_line(line: str) -> bool:
    return _extract_timestamp(line) is not None


def _line_has_thread_id(line: str, thread_id: str) -> bool:
    return _extract_thread_id(line) == thread_id


def _section_name_from_keyword(keyword: str) -> str:
    if keyword == IR_DEF_START:
        return "ir_table_definition"
    if keyword == IR_RESULT_START:
        return "generated_ir"
    return keyword
