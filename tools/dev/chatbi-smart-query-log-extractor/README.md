# ChatBI 智能问数关键日志提取工具

## Purpose

针对 ChatBI 智能问数日志，从一份纯文本日志中按“精确问题文本 + 请求 ID”提取关键链路信息，并输出结构化 JSON 与可读 HTML 页面。

## Scenarios

- 排查同一问题多次提问时各次调用的差异
- 快速回看某次问数调用的 RAG、改写、召回表、Prompt 与 IR 结果
- 为后续 skill 或大模型工作流提供稳定的结构化日志抽取结果

## Prerequisites

- Python 3.10+
- 可读取的纯文本日志文件

## Usage

```text
python -m chatbi_smart_query_log_extractor --log <log-file> --question "<exact question>" [--output-dir <dir>] [--encoding <name>] [--json-only] [--html-only]
```

## Inputs

- `--log`: 纯文本日志文件路径
- `--question`: 需要精确匹配的问数问题
- `--output-dir`: 输出目录，默认 `output/`
- `--encoding`: 显式指定日志编码；未指定时自动尝试 `utf-8`、`utf-8-sig`、`gbk`、`gb18030`

## Outputs

- `*.json`: 结构化提取结果
- `*.html`: 按调用 ID 分块的排障页面

## Examples

```text
python -m chatbi_smart_query_log_extractor --log .\chatbi.log --question "近7天销售额是多少" --output-dir .\output
```

该命令会从日志中匹配锚点日志，识别 15 位请求 ID，并生成 JSON 与 HTML 两份结果。

## Side Effects

- 创建输出目录
- 写出 JSON 与 HTML 文件

## Limitations

- 问题文本按字面值精确匹配，不做模糊匹配或同义改写
- 锚点关键词按 `sql_template_matc` 字面值处理
- 多行块依赖日志关键字边界；若终止标记缺失，会收集到文件末尾并记录解析错误

## Status

`temporary`
