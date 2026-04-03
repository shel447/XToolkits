# Tool Catalog Conventions

## 1. Design Goals

The repository should support three workflows at the same time:

- a human quickly finding the right tool
- a developer understanding how to run and maintain it
- a skill or LLM workflow understanding how to call it safely

This means every self-developed tool needs:

- a readable `README.md`
- a machine-readable `tool.yaml`
- a stable CLI entry pattern

## 2. Directory Rules

### Promote into `tools/`

Put a tool under `tools/<category>/<tool-id>/` when all of the following are true:

- it is self-developed or actively maintained here
- it has reuse value beyond a single throwaway task
- it is worth keeping documented and callable

### Keep as `project-reference`

Do not promote into `tools/` when the utility:

- only makes sense inside one business project
- depends heavily on that project's private context
- is not expected to be reused outside that scenario

For those cases, keep the source in its original project and register it in the catalog.

## 3. Status Rules

Use these lifecycle states consistently:

- `active`: normal maintained state
- `temporary`: short-lived utility for a limited task or phase
- `sunset`: stop extending it; cleanup candidate
- `deprecated`: do not use for new work, kept only for compatibility or reference
- `archived`: historical only

### Temporary Tool Policy

Temporary tools are allowed, but they must still have:

- a `tool.yaml`
- a minimal README
- a clear `status = temporary`
- a project or scenario note in `projects.md`

Temporary tools should be part of a regular review pass. At each review, choose one action:

1. promote it to `active`
2. mark it `sunset`
3. archive or remove it

## 4. Tool Contract

All self-developed tools should expose a stable CLI contract first. The default integration target is:

- human terminal usage
- script orchestration
- future skill wrapping
- future LLM invocation through structured metadata

### CLI Design Rules

- Prefer explicit subcommands or explicit flags over positional-only magic.
- Keep names stable and descriptive.
- Prefer deterministic output when possible.
- When structured output exists, provide a JSON mode or a clearly documented file output.
- Exit codes must have documented meaning.
- Side effects must be explicit.

### Required `tool.yaml` Fields

```yaml
id: sample-tool
name: Sample Tool
summary: One-line statement of what the tool does.
type: script
scope: shared
category: dev
status: active
project:
tags: []
runtime: powershell
entrypoint: .\run.ps1
created_at: 2026-04-03
last_verified_at:
interface:
  command: .\run.ps1
  args:
    - name: input
      required: true
      description: Path to the input file.
    - name: output
      required: false
      description: Path to the output file.
  input:
    kind: file
    format: txt
  output:
    kind: file
    format: json
  exit_codes:
    0: success
    2: validation_error
    3: runtime_error
  side_effects:
    - writes output files
  examples:
    - command: .\run.ps1 -Input .\in.txt -Output .\out.json
      description: Convert one text file into JSON output.
dependencies: []
artifacts: []
```

### Field Intent

- `type`: `script | app | external | service`
- `scope`: `shared | external | project-reference`
- `status`: lifecycle state used for maintenance and cleanup
- `project`: owning or related project when applicable
- `runtime`: execution environment such as `python`, `powershell`, `node`, or `exe`
- `entrypoint`: primary launch target
- `interface`: minimum contract for future automation and model wrapping
- `artifacts`: outputs or generated files worth tracking

## 5. README Requirements

Every self-developed tool README should contain:

1. purpose
2. applicable scenarios
3. prerequisites and dependencies
4. usage syntax
5. input and output description
6. examples
7. side effects and limitations
8. status and maintenance note

## 6. Naming Rules

- Use lowercase kebab-case for `tool-id`.
- Keep IDs stable once published in the catalog.
- Use category names for broad capability, not team or project names.
- Put project affiliation in metadata, not in the top-level category.

## 7. Review Routine

Run a periodic catalog review, usually weekly or monthly:

1. list all tools with `status = temporary`
2. list all tools with `status = sunset`
3. check whether the related project or scenario is still active
4. decide promote, archive, or remove

This review should be driven from catalog data, not memory.
