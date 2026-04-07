from __future__ import annotations

import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


TOOL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXECUTORS_CONFIG = TOOL_ROOT / "executors.local.yaml"
SQL_RESULT_ANCHOR = "resulted_sql = to_sql(intent_result)"
SQL_RESULT_PRINT = "print(resulted_sql)"

_LOCKS_GUARD = threading.Lock()
_EXECUTOR_LOCKS: dict[str, threading.Lock] = {}


class ExecutorConfigError(RuntimeError):
    pass


class IRExecutionRequestError(RuntimeError):
    pass


def execute_complete_ir(
    report: dict[str, Any],
    match_id: str,
    executor_name: str | None = None,
    source_filename: str | None = None,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    match = _find_match(report, match_id)
    complete_ir = match.get("complete_ir", "") if match is not None else ""
    if not complete_ir:
        raise IRExecutionRequestError(f"complete_ir not found for match_id: {match_id}")

    thread_id = str(match.get("thread_id", "")) if match is not None else ""

    config = _load_executors_config(config_path)
    executor_id, executor = _resolve_executor_config(config, executor_name)
    resolved_filename = _normalize_source_filename(source_filename)
    enhanced_source = _inject_result_print(complete_ir)

    project_root = _resolve_existing_dir(executor, "project_root")
    working_dir = _resolve_existing_dir(executor, "working_dir")
    target_dir = _resolve_or_create_dir(executor, "target_dir")
    python_bin = _resolve_existing_file(executor, "python_bin")
    timeout_sec = _resolve_timeout_sec(executor)
    result_encoding = _resolve_result_encoding(executor)
    target_file = (target_dir / resolved_filename).resolve()

    placeholders = {
        "project_root": str(project_root),
        "working_dir": str(working_dir),
        "target_dir": str(target_dir),
        "target_file": str(target_file),
        "python_bin": str(python_bin),
        "pathsep": os.pathsep,
    }
    run_command = _resolve_run_command(executor, placeholders)
    execution_env = _resolve_execution_env(executor, placeholders)

    start = time.perf_counter()
    lock = _get_executor_lock(f"{Path(config_path or DEFAULT_EXECUTORS_CONFIG).resolve()}::{executor_id}")
    try:
        with lock:
            target_file.write_text(enhanced_source, encoding="utf-8")
            completed = subprocess.run(
                run_command,
                cwd=working_dir,
                env=execution_env,
                capture_output=True,
                text=False,
                timeout=timeout_sec,
                check=False,
            )
    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return {
            "match_id": match_id,
            "thread_id": thread_id,
            "executor": executor_id,
            "success": False,
            "exit_code": -1,
            "duration_ms": duration_ms,
            "stdout": _decode_output(exc.stdout, result_encoding),
            "stderr": _decode_output(exc.stderr, result_encoding) or f"Execution timed out after {timeout_sec}s",
            "target_file": str(target_file),
        }

    duration_ms = int((time.perf_counter() - start) * 1000)
    stdout = _decode_output(completed.stdout, result_encoding)
    stderr = _decode_output(completed.stderr, result_encoding)
    return {
        "match_id": match_id,
        "thread_id": thread_id,
        "executor": executor_id,
        "success": completed.returncode == 0,
        "exit_code": completed.returncode,
        "duration_ms": duration_ms,
        "stdout": stdout,
        "stderr": stderr,
        "target_file": str(target_file),
    }


def _find_match(report: dict[str, Any], match_id: str) -> dict[str, Any] | None:
    for question_group in report.get("questions", []):
        for match in question_group.get("matches", []):
            if match.get("match_id") == match_id:
                return match
    return None


def _load_executors_config(config_path: str | Path | None) -> dict[str, Any]:
    path = Path(config_path) if config_path is not None else DEFAULT_EXECUTORS_CONFIG
    if not path.is_file():
        raise ExecutorConfigError(f"executors.local.yaml not found: {path}")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ExecutorConfigError(f"failed to parse executor config: {exc}") from exc
    if not isinstance(payload, dict):
        raise ExecutorConfigError("executor config root must be a mapping")
    return payload


def _resolve_executor_config(payload: dict[str, Any], executor_name: str | None) -> tuple[str, dict[str, Any]]:
    default_executor = payload.get("default_executor")
    executors = payload.get("executors")
    if not isinstance(executors, dict) or not executors:
        raise ExecutorConfigError("executors config must contain a non-empty 'executors' mapping")

    resolved_name = executor_name.strip() if isinstance(executor_name, str) and executor_name.strip() else default_executor
    if not isinstance(resolved_name, str) or not resolved_name:
        raise ExecutorConfigError("default_executor is missing or invalid")

    executor = executors.get(resolved_name)
    if not isinstance(executor, dict):
        raise ExecutorConfigError(f"executor '{resolved_name}' not found in config")
    return resolved_name, executor


def _normalize_source_filename(source_filename: str | None) -> str:
    if source_filename is None or not source_filename.strip():
        return _default_source_filename()

    filename = source_filename.strip()
    if "/" in filename or "\\" in filename or ".." in filename:
        raise IRExecutionRequestError("source_filename must be a file name only and cannot contain path segments")
    if filename in {".", ".."}:
        raise IRExecutionRequestError("source_filename is invalid")
    if not filename.endswith(".py"):
        filename = f"{filename}.py"
    return filename


def _default_source_filename() -> str:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    return f"case_{timestamp}.py"


def _inject_result_print(source: str) -> str:
    lines = source.splitlines()
    matching_indexes = [index for index, line in enumerate(lines) if line.strip() == SQL_RESULT_ANCHOR]
    if not matching_indexes:
        raise IRExecutionRequestError(f"complete_ir missing anchor line: {SQL_RESULT_ANCHOR}")
    if len(matching_indexes) > 1:
        raise IRExecutionRequestError(f"complete_ir contains multiple anchor lines: {SQL_RESULT_ANCHOR}")

    anchor_index = matching_indexes[0]
    indent = lines[anchor_index][: len(lines[anchor_index]) - len(lines[anchor_index].lstrip())]
    lines.insert(anchor_index + 1, f"{indent}{SQL_RESULT_PRINT}")
    enhanced = "\n".join(lines)
    if source.endswith("\n"):
        enhanced += "\n"
    return enhanced


def _resolve_existing_dir(executor: dict[str, Any], key: str) -> Path:
    value = executor.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ExecutorConfigError(f"executor field '{key}' is missing or invalid")
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise ExecutorConfigError(f"executor field '{key}' points to a missing directory: {path}")
    return path


def _resolve_or_create_dir(executor: dict[str, Any], key: str) -> Path:
    value = executor.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ExecutorConfigError(f"executor field '{key}' is missing or invalid")
    path = Path(value).expanduser().resolve()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ExecutorConfigError(f"failed to prepare '{key}' directory: {path} ({exc})") from exc
    if not path.is_dir():
        raise ExecutorConfigError(f"executor field '{key}' is not a directory: {path}")
    return path


def _resolve_existing_file(executor: dict[str, Any], key: str) -> Path:
    value = executor.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ExecutorConfigError(f"executor field '{key}' is missing or invalid")
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ExecutorConfigError(f"executor field '{key}' points to a missing file: {path}")
    return path


def _resolve_timeout_sec(executor: dict[str, Any]) -> int:
    raw_value = executor.get("timeout_sec", 60)
    if not isinstance(raw_value, int) or raw_value <= 0:
        raise ExecutorConfigError("executor field 'timeout_sec' must be a positive integer")
    return raw_value


def _resolve_result_encoding(executor: dict[str, Any]) -> str:
    value = executor.get("result_encoding", "utf-8")
    if not isinstance(value, str) or not value.strip():
        raise ExecutorConfigError("executor field 'result_encoding' must be a non-empty string")
    return value.strip()


def _resolve_run_command(executor: dict[str, Any], placeholders: dict[str, str]) -> list[str]:
    raw_command = executor.get("run_command")
    if not isinstance(raw_command, list) or not raw_command:
        raise ExecutorConfigError("executor field 'run_command' must be a non-empty list")

    command: list[str] = []
    for token in raw_command:
        if not isinstance(token, str) or not token:
            raise ExecutorConfigError("executor field 'run_command' must contain non-empty strings")
        command.append(_format_template(token, placeholders, "executor field 'run_command'"))
    return command


def _resolve_execution_env(executor: dict[str, Any], placeholders: dict[str, str]) -> dict[str, str]:
    env = dict(os.environ)
    raw_env = executor.get("env", {})
    if raw_env is None:
        raw_env = {}
    if not isinstance(raw_env, dict):
        raise ExecutorConfigError("executor field 'env' must be a mapping if provided")

    custom_pythonpath = ""
    for key, value in raw_env.items():
        if not isinstance(key, str) or not key.strip():
            raise ExecutorConfigError("executor field 'env' must contain non-empty string keys")
        if not isinstance(value, str):
            raise ExecutorConfigError("executor field 'env' must contain string values")
        resolved_key = key.strip()
        resolved_value = _format_template(value, placeholders, f"executor field 'env.{resolved_key}'")
        if resolved_key == "PYTHONPATH":
            custom_pythonpath = resolved_value
            continue
        env[resolved_key] = resolved_value

    env["PYTHONPATH"] = _merge_pythonpath(
        custom_pythonpath,
        [placeholders["project_root"], placeholders["working_dir"]],
        env.get("PYTHONPATH", ""),
    )
    return env


def _merge_pythonpath(custom_value: str, default_entries: list[str], inherited_value: str) -> str:
    merged: list[str] = []
    for segment in [custom_value, *default_entries, inherited_value]:
        for entry in segment.split(os.pathsep):
            normalized = entry.strip()
            if normalized and normalized not in merged:
                merged.append(normalized)
    return os.pathsep.join(merged)


def _format_template(template: str, placeholders: dict[str, str], field_name: str) -> str:
    try:
        return template.format(**placeholders)
    except KeyError as exc:
        raise ExecutorConfigError(f"{field_name} contains unsupported placeholder: {exc.args[0]}") from exc


def _decode_output(raw: bytes | None, encoding: str) -> str:
    if raw is None:
        return ""
    return raw.decode(encoding, errors="replace")


def _get_executor_lock(key: str) -> threading.Lock:
    with _LOCKS_GUARD:
        lock = _EXECUTOR_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _EXECUTOR_LOCKS[key] = lock
        return lock
