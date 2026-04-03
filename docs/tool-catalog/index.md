# Tool Catalog

This is the master list of tools in XToolkits. The primary navigation is by capability. Secondary navigation by project lives in `projects.md`.

## Catalog Columns

Use the following columns for every catalog row:

| Tool ID | Name | Category | Scope | Type | Status | Summary | Project | Location |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Categories

### Automation

Automation scripts, scheduled helpers, workflow orchestration, task batching.

| Tool ID | Name | Category | Scope | Type | Status | Summary | Project | Location |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

### Data

Data extraction, transformation, validation, report helpers, structured conversion.

| Tool ID | Name | Category | Scope | Type | Status | Summary | Project | Location |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

### Dev

Developer workflow helpers, build helpers, local environment tools, test helpers.

| Tool ID | Name | Category | Scope | Type | Status | Summary | Project | Location |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `chatbi-smart-query-log-extractor` | ChatBI Smart Query Log Extractor | `dev` | `shared` | `script` | `temporary` | 按精确问题和 15 位请求 ID 提取 ChatBI 问数关键日志，并生成 JSON/HTML 结果。 | `ChatBI` | `tools/dev/chatbi-smart-query-log-extractor/` |

### File

Batch file operations, rename tools, sync helpers, path utilities, packaging helpers.

| Tool ID | Name | Category | Scope | Type | Status | Summary | Project | Location |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

### Media

Image, audio, video, document rendering, conversion, capture, and post-processing tools.

| Tool ID | Name | Category | Scope | Type | Status | Summary | Project | Location |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

### System

Environment inspection, system diagnostics, machine setup, process helpers, OS utilities.

| Tool ID | Name | Category | Scope | Type | Status | Summary | Project | Location |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

### Text

Text cleanup, parsing, templating, prompt utilities, encoding conversion, extraction.

| Tool ID | Name | Category | Scope | Type | Status | Summary | Project | Location |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Scope Rules

- `shared`: self-developed or maintained here for repeated use
- `external`: third-party tool only tracked in the catalog
- `project-reference`: tied to a specific project or scenario and not promoted into `tools/`

## Maintenance View

When reviewing the catalog, prioritize:

1. all rows with `status = temporary`
2. all rows with `status = sunset`
3. all rows missing `last_verified_at` in their `tool.yaml`
