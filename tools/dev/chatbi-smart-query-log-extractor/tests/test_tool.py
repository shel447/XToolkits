import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = TOOL_ROOT / ".tmp-test-artifacts"
FIXTURES_ROOT = TOOL_ROOT / "tests" / "fixtures"
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from chatbi_smart_query_log_extractor.__main__ import main
from chatbi_smart_query_log_extractor.extractor import extract_report
from chatbi_smart_query_log_extractor.html_report import render_html


QUESTION = "近7天销售额是多少"
ALT_QUESTION = "近7天销售额是多少?"
FULL_LOG = """2026-04-02 19:00:01.665 [INFO] [123456789012345] sql_template_match hit query: 近7天销售额是多少
2026-04-02 19:00:01.700 [INFO] [123456789012345] knowledge retriever success retrieved docs: sales_doc, shop_doc
2026-04-02 19:00:01.710 [INFO] [123456789012345] rewrite question from [old] [new] 请查询近7天销售额
2026-04-02 19:00:01.720 [INFO] [123456789012345] Schema链接完成
2026-04-02 19:00:01.730 [INFO] [123456789012345] 召回表: sales_order, shop_dim
2026-04-02 19:00:01.740 [INFO] [123456789012345] 表定义的IR
table sales_order(id, amount)
table shop_dim(shop_id, shop_name)
2026-04-02 19:00:01.760 [INFO] [123456789012345] code guardrail check result safe
2026-04-02 19:00:01.770 [INFO] [123456789012345] 生成器任务：{"messages": [{"role": "system", "content": "你是助手\\n请生成IR"}, {"role": "user", "content": "问题：近7天销售额\\n请输出\\\\\\"IR\\\\\\""}]}
2026-04-02 19:00:01.780 [INFO] [123456789012345] 推理结果
SELECT amount FROM sales_order
return result
2026-04-02 19:05:01.665 [INFO] [223456789012345] sql_template_match hit query: 近7天销售额是多少
2026-04-02 19:05:01.710 [INFO] [223456789012345] rewrite question from [old] [new] 帮我查询近7天销售额
2026-04-02 19:05:01.770 [INFO] [223456789012345] 生成器任务：{"messages": [{"role": "system", "content": "系统提示\\n第二次"}, {"role": "user", "content": "用户问题\\n第二次"}]}
2026-04-02 19:05:01.780 [INFO] [223456789012345] 推理结果
SELECT amount FROM sales_order WHERE ds >= current_date - 7
return result
"""

PARTIAL_LOG = """2026-04-02 20:00:01.665 [INFO] [323456789012345] sql_template_match hit query: 近7天销售额是多少
2026-04-02 20:00:01.770 [INFO] [323456789012345] 生成器任务：not-a-json-payload
2026-04-02 20:00:01.780 [INFO] [323456789012345] 推理结果
SELECT broken FROM data
"""


class ExtractorTests(unittest.TestCase):
    def test_extract_report_handles_complex_fixture_file(self) -> None:
        log_text = (FIXTURES_ROOT / "complex_chatbi.log").read_text(encoding="utf-8")

        report = extract_report(log_text, "complex_chatbi.log")

        self.assertEqual(report["total_questions"], 2)
        self.assertEqual(
            [question["question"] for question in report["questions"]],
            [QUESTION, ALT_QUESTION],
        )

        first_group = report["questions"][0]
        self.assertEqual(first_group["question"], QUESTION)
        self.assertEqual(first_group["total_matches"], 2)
        self.assertEqual(
            [match["request_id"] for match in first_group["matches"]],
            ["423456789012345", "523456789012345"],
        )

        first = first_group["matches"][0]
        self.assertEqual(len(first["rag_results"]), 2)
        self.assertEqual(first["rewritten_question"], "请帮我统计最近7天销售额")
        self.assertEqual(first["recalled_tables"], ["2026-04-03 09:15:00.050 [INFO] [423456789012345] Schema链接完成", "sales_order", "dim_calendar"])
        self.assertIn("join sales_order.ds = dim_calendar.ds", first["ir_table_definition"])
        self.assertEqual(first["parse_errors"], [])

        second = first_group["matches"][1]
        self.assertEqual(second["final_prompt"]["system"], "系统角色\n路径：\\\\server\\share\\prompt.txt")
        self.assertEqual(second["final_prompt"]["user"], '请输出"门店销售额" IR\n并保留 shop_id')
        self.assertIn("shop_id", second["generated_ir"])
        self.assertNotIn("推理结果", second["generated_ir"])

        second_group = report["questions"][1]
        self.assertEqual(second_group["question"], ALT_QUESTION)
        self.assertEqual(second_group["total_matches"], 1)
        third = second_group["matches"][0]
        self.assertIn("rag_results", third["missing_sections"])
        self.assertIn("rewritten_question", third["missing_sections"])
        self.assertIn("final_prompt: failed to parse payload", "".join(third["parse_errors"]))
        self.assertIn("ir_table_definition: missing terminator", "".join(third["parse_errors"]))
        self.assertIn("generated_ir: missing terminator", "".join(third["parse_errors"]))

    def test_extract_report_collects_expected_sections_for_multiple_calls(self) -> None:
        report = extract_report(FULL_LOG, "sample.log", question_filter=QUESTION)

        self.assertEqual(report["total_questions"], 1)
        self.assertEqual(len(report["questions"]), 1)
        self.assertEqual(report["questions"][0]["question"], QUESTION)
        self.assertEqual(report["questions"][0]["total_matches"], 2)

        first = report["questions"][0]["matches"][0]
        self.assertEqual(first["request_id"], "123456789012345")
        self.assertEqual(first["anchor_timestamp"], "2026-04-02 19:00:01.665")
        self.assertIn("knowledge retriever success", first["rag_results"][0])
        self.assertEqual(first["rewritten_question"], "请查询近7天销售额")
        self.assertIn("sales_order, shop_dim", first["recalled_tables"])
        self.assertIn("表定义的IR", first["ir_table_definition"])
        self.assertNotIn("code guardrail check result", first["ir_table_definition"])
        self.assertEqual(first["final_prompt"]["system"], "你是助手\n请生成IR")
        self.assertEqual(first["final_prompt"]["user"], '问题：近7天销售额\n请输出"IR"')
        self.assertIn("你是助手\n请生成IR", first["final_prompt"]["combined"])
        self.assertTrue(first["generated_ir"].startswith("SELECT amount FROM sales_order"))
        self.assertIn("return result", first["generated_ir"])
        self.assertNotIn("推理结果", first["generated_ir"])
        self.assertEqual(first["missing_sections"], [])
        self.assertEqual(first["parse_errors"], [])

        second = report["questions"][0]["matches"][1]
        self.assertEqual(second["request_id"], "223456789012345")
        self.assertEqual(second["anchor_timestamp"], "2026-04-02 19:05:01.665")
        self.assertIn("rag_results", second["missing_sections"])
        self.assertIn("ir_table_definition", second["missing_sections"])

    def test_extract_report_marks_partial_failures_and_preserves_prompt_raw_text(self) -> None:
        report = extract_report(PARTIAL_LOG, "partial.log")

        self.assertEqual(report["total_questions"], 1)
        self.assertEqual(report["questions"][0]["question"], QUESTION)
        match = report["questions"][0]["matches"][0]
        self.assertIn("rag_results", match["missing_sections"])
        self.assertIn("rewritten_question", match["missing_sections"])
        self.assertIn("final_prompt", "".join(match["parse_errors"]))
        self.assertEqual(match["final_prompt"]["raw"], "not-a-json-payload")
        self.assertIn("SELECT broken FROM data", match["generated_ir"])
        self.assertIn("generated_ir", "".join(match["parse_errors"]))

    def test_extract_report_returns_zero_questions_when_filter_not_found(self) -> None:
        report = extract_report(FULL_LOG, "sample.log", question_filter="不存在的问题")

        self.assertEqual(report["total_questions"], 0)
        self.assertEqual(report["questions"], [])

    def test_render_html_shows_navigation_prompt_and_missing_markers(self) -> None:
        report = extract_report((FIXTURES_ROOT / "complex_chatbi.log").read_text(encoding="utf-8"), "complex_chatbi.log")
        html = render_html(report)

        self.assertIn("近7天销售额是多少", html)
        self.assertIn("近7天销售额是多少?", html)
        self.assertIn("423456789012345", html)
        self.assertIn('href="#question-1"', html)
        self.assertIn('href="#question-2"', html)
        self.assertIn("最终 Prompt", html)
        self.assertIn("未命中该字段", html)


class CliTests(unittest.TestCase):
    def test_main_returns_no_match_exit_code(self) -> None:
        TMP_ROOT.mkdir(exist_ok=True)
        temp_dir = TMP_ROOT / f"run-{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=False)
        try:
            log_path = temp_dir / "empty.log"
            log_path.write_text(FULL_LOG, encoding="utf-8")

            exit_code = main(
                [
                    "--log",
                    str(log_path),
                    "--question",
                    "不存在的问题",
                    "--output-dir",
                    str(temp_dir),
                ]
            )

            self.assertEqual(exit_code, 3)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_cli_generates_html_and_json_with_gbk_fallback(self) -> None:
        TMP_ROOT.mkdir(exist_ok=True)
        temp_dir = TMP_ROOT / f"run-{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=False)
        try:
            log_path = temp_dir / "gbk.log"
            output_dir = temp_dir / "out"
            output_dir.mkdir()
            log_path.write_bytes(FULL_LOG.encode("gbk"))

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "chatbi_smart_query_log_extractor",
                    "--log",
                    str(log_path),
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=TOOL_ROOT,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 4)
            json_files = list(output_dir.glob("*.json"))
            html_files = list(output_dir.glob("*.html"))
            self.assertEqual(len(json_files), 1)
            self.assertEqual(len(html_files), 1)

            payload = json.loads(json_files[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["total_questions"], 1)
            self.assertEqual(payload["questions"][0]["question"], QUESTION)
            self.assertEqual(payload["questions"][0]["matches"][0]["request_id"], "123456789012345")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
