# Project Reverse Index

Use this file to answer: "what tools exist for a given project, scenario, or temporary effort?"

## Index Columns

| Project | Tool ID | Name | Status | Scope | Role | Location | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `ChatBI` | `chatbi-smart-query-log-extractor` | ChatBI Smart Query Log Extractor | `temporary` | `shared` | `debug` | `tools/dev/chatbi-smart-query-log-extractor/` | 按精确问题提取同题多次调用的关键日志链路，输出 JSON 和 HTML 页面。 |

## Usage Rules

- Add one row for every project-specific tool or reference.
- Include reusable tools here too when they are important to a project workflow.
- For short-lived utilities, make the status visible here even if the tool code lives elsewhere.

## Suggested Roles

- `build`
- `run`
- `debug`
- `data-fix`
- `migration`
- `one-off`
- `ops`
- `delivery`

## Review Focus

During periodic cleanup, review all rows where:

- `status = temporary`
- `status = sunset`
- the project is already inactive or closed
