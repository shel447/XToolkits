# ChatBI 智能问数关键日志提取工具

## Purpose

针对 ChatBI 智能问数日志，自动发现日志中的唯一问题文本，再按“问题 -> 请求 ID”提取关键链路信息，并输出结构化 JSON 与可读 HTML 页面。

## Scenarios

- 排查同一问题多次提问时各次调用的差异
- 快速回看某次问数调用的 RAG、改写、召回表、Prompt、生成 IR 与完整 IR
- 为后续 skill 或大模型工作流提供稳定的结构化日志抽取结果

## Prerequisites

- Python 3.10+
- 可读取的纯文本日志文件

## Usage

```text
python -m chatbi_smart_query_log_extractor --log <log-file> [--question "<exact question>"] [--output-dir <dir>] [--encoding <name>] [--json-only] [--html-only]
```

## Inputs

- `--log`: 纯文本日志文件路径
- `--question`: 可选；仅提取该精确问题对应的日志链路。未提供时，工具会自动发现日志中的全部唯一问题
- `--output-dir`: 输出目录，默认 `output/`
- `--encoding`: 显式指定日志编码；未指定时自动尝试 `utf-8`、`utf-8-sig`、`gbk`、`gb18030`

## Outputs

- `*.json`: 顶层按问题分组的结构化提取结果，调用级结果包含 `ir_table_definition`、`generated_ir`、`complete_ir`
- `*.html`: 先按问题分组、再按调用 ID 分块的排障页面；`RAG 检索结果`、`IR 表定义`、`最终 Prompt`、`生成 IR 结果` 默认折叠，按需展开查看；`完整 IR` 右上角提供复制按钮

## Examples

```text
python -m chatbi_smart_query_log_extractor --log .\chatbi.log --output-dir .\output
```

该命令会从包含 `sql_template_match` 的锚点日志中自动发现全部唯一问题，识别每个问题对应的 15 位请求 ID，并生成 JSON 与 HTML 两份结果。

```text
python -m chatbi_smart_query_log_extractor --log .\chatbi.log --question "近7天销售额是多少" --output-dir .\output
```

该命令会只保留目标问题对应的问题分组，并继续提取该问题下的多次调用。

## Side Effects

- 创建输出目录
- 写出 JSON 与 HTML 文件

## Limitations

- 问题文本按字面值精确匹配，不做模糊匹配或同义改写
- 自动发现只识别包含 `sql_template_match` 的锚点日志，并从首个 `query: ` 之后提取问题文本
- 最终 Prompt 只识别包含 `生成器任务：` 的日志行，并兼容 JSON 或 Python 对象直接序列化后的单引号消息体；会分别提取前两条 message 的 `content`
- `IR 表定义` 从 `表定义的IR：` 之后开始提取，不保留关键词前缀
- `生成 IR 结果` 从 `最终的IR` 之后开始提取，到 `tables = get_tables_columns(table_exprs)` 为止，并保留结束行
- `完整 IR` 不是直接从日志中提取，而是把 `IR 表定义` 插入 `生成 IR 结果` 中 `@dataclass` 行之前，插入块前后各保留一个空行；`@dataclass` 之前的生成前导内容不会保留到 `complete_ir`

## Status

`temporary`
