# XToolkits

XToolkits is a toolkit workspace for collecting small utilities used in daily work. It covers three kinds of assets:

- self-developed reusable tools
- external tools worth cataloging
- project-specific tool references worth tracking

The repository is organized for two consumers at the same time:

- humans who need to quickly find "what can solve this problem"
- skills or LLM workflows that need a stable tool contract

## Repository Layout

```text
docs/
  tool-catalog/
    index.md
    projects.md
    conventions.md
tools/
  automation/
  data/
  dev/
  file/
  media/
  system/
  text/
templates/
  tool/
scripts/
  catalog/
```

## Entry Points

- `docs/tool-catalog/index.md`: master catalog organized by capability
- `docs/tool-catalog/projects.md`: reverse index by project or scenario
- `docs/tool-catalog/conventions.md`: catalog rules, lifecycle rules, and tool contract
- `templates/tool/`: starting point for adding a new self-developed tool

## Collection Rules

- Put long-lived self-developed tools under `tools/<category>/<tool-id>/`.
- Track external tools in the catalog, but do not copy third-party code into this repository unless there is a clear need.
- Track project-specific short-lived utilities in the catalog first. Only promote them into `tools/` when they become reusable or worth maintaining.

## Add A Tool

1. Choose the category under `tools/` if the tool belongs in this repository.
2. Copy `templates/tool/` into a new tool directory.
3. Fill in `tool.yaml` with a stable CLI contract.
4. Fill in `README.md` with usage, examples, inputs, outputs, and limits.
5. Register the tool in `docs/tool-catalog/index.md`.
6. If the tool is tied to a project or short-lived work, also register it in `docs/tool-catalog/projects.md`.

## Lifecycle

- `active`: recommended and maintained
- `temporary`: short-lived utility, kept for near-term work
- `sunset`: scheduled for cleanup or replacement
- `deprecated`: retained only for compatibility or reference
- `archived`: no longer active, kept only as historical record

Temporary and sunset tools should be reviewed on a regular cadence and either promoted, archived, or removed.
