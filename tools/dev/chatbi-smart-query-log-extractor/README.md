# ChatBI 智能问数关键日志提取工具

## Purpose

针对 ChatBI 智能问数日志，自动发现日志中的唯一问题文本，再按“问题 -> 调用窗口”提取关键链路信息，并输出结构化 JSON 与可读 HTML 页面。

## Scenarios

- 排查同一问题多次提问时各次调用的差异
- 快速回看某次问数调用的 RAG、改写、召回表、Prompt、生成 IR 与完整 IR
- 为后续 skill 或大模型工作流提供稳定的结构化日志抽取结果

## Prerequisites

- Python 3.10+
- 可读取的纯文本日志文件
- `requests`
- `PyYAML`

## Usage

```text
python -m chatbi_smart_query_log_extractor --log <log-file> [--question "<exact question>"] [--output-dir <dir>] [--encoding <name>] [--json-only] [--html-only]
python -m chatbi_smart_query_log_extractor --serve [--log <initial-log-file>] [--host <host>] [--port <port>]
```

## Inputs

- `--log`: 纯文本日志文件路径；静态产物模式下必填。配合 `--serve` 时可选，作为初始预加载日志
- `--question`: 可选；仅提取该精确问题对应的日志链路。未提供时，工具会自动发现日志中的全部唯一问题
- `--output-dir`: 输出目录，默认 `output/`
- `--encoding`: 显式指定日志编码；未指定时自动尝试 `utf-8`、`utf-8-sig`、`gbk`、`gb18030`
- `--json-only`: 仅输出 JSON
- `--html-only`: 仅输出 HTML
- `--serve`: 生成结果后启动本地交互服务，支持在页面中执行“最终 Prompt”
- `--host`: 本地交互服务监听地址，默认 `127.0.0.1`
- `--port`: 本地交互服务监听端口，默认 `8000`

## Outputs

- `*.json`: 顶层按问题分组的结构化提取结果，调用级结果包含 `thread_id`、`associated_thread_ids`、`match_id`、`rewrite_questions`、`flow_status`、`retry_count`、`verifier_failures`、`ir_table_definition`、`generated_ir`、`complete_ir`
- `*.html`: 静态排障页面，先按问题分组、再按调用窗口分块展示；问题导航会显示成功/失败图标与重试次数徽标，适合直接打开查看基本信息
- `--serve` 页面：固定单端口常驻服务页面，可从浏览器选择日志文件或日志目录中的某个文件，再动态解析；交互能力包括 Prompt 执行、完整 IR 执行、双复制入口等

## Examples

```text
python -m chatbi_smart_query_log_extractor --log .\chatbi.log --output-dir .\output
```

该命令会自动发现日志中的问题，并优先按 `call sqlflow input:` 识别主调用边界；如果主线程分解出子线程，还会把命中的子线程一起归并回同一次调用。调用的展示锚点、时间和 `match_id` 仍然保持为原始 `sql_template_match` 命中日志。

```text
python -m chatbi_smart_query_log_extractor --log .\chatbi.log --question "近7天销售额是多少" --output-dir .\output
```

该命令会只保留目标问题对应的问题分组，并继续提取该问题下的多次调用。

```text
python -m chatbi_smart_query_log_extractor --log .\chatbi.log --output-dir .\output --serve
```

该命令会在写出结果后启动本地交互服务，并预加载这一份日志。浏览器打开 `http://127.0.0.1:8000/` 后，可以继续切换其他日志文件或目录中的文件。

```text
python -m chatbi_smart_query_log_extractor --serve
```

该命令会直接启动一个空白的日志浏览服务。浏览器打开 `http://127.0.0.1:8000/` 后，可以从页面上选择单个日志文件，或先选择日志目录再从列表里点选某个文件进行解析。

## Local Executor Config

- 复制 [executors.example.yaml](E:\code\codex_projects\XToolkits\tools\dev\chatbi-smart-query-log-extractor\executors.example.yaml) 为同目录下的 `executors.local.yaml`
- `executors.local.yaml` 不纳入版本控制，专门保存本机的项目路径、解释器路径和执行命令
- 执行完整 IR 时，工具会默认把 `project_root` 和 `working_dir` 预置到子进程的 `PYTHONPATH`，用来贴近 PyCharm 里“内容根/源码根”可导入的效果；像 `import src.xxx` 这类项目内导入通常不需要再额外补路径
- 如果目标项目还依赖额外环境变量，可以在执行器里补 `env` 映射；这些值也支持占位符
- `run_command` 支持这些占位符：
  - `{python_bin}`
  - `{target_file}`
  - `{project_root}`
  - `{working_dir}`
  - `{target_dir}`
  - `{pathsep}`

示例：

```yaml
default_executor: demo
executors:
  demo:
    project_root: E:/code/codex_projects/your-target-project
    working_dir: E:/code/codex_projects/your-target-project
    target_dir: E:/code/codex_projects/your-target-project/tmp/generated_ir
    python_bin: E:/code/codex_projects/your-target-project/.venv/Scripts/python.exe
    run_command:
      - "{python_bin}"
      - "{target_file}"
    env:
      APP_ENV: local
      # PYTHONPATH: "{project_root}{pathsep}E:/code/codex_projects/your-target-project/extra_src"
    timeout_sec: 60
    result_encoding: utf-8
```

如果你在 PyCharm 里手工执行生成文件能跑，但工具执行时报 `No module named 'src'`，优先检查两点：

- `working_dir` 是否与 PyCharm Configuration 的 Working directory 一致
- 你的项目除了根目录外，是否还依赖额外源码目录；如果有，就在 `env.PYTHONPATH` 里补上

页面执行“完整 IR”时，工具会把 `complete_ir` 写到 `target_dir/<源文件名>`。如果你没有输入文件名，会自动生成 `case_<紧凑时间戳>.py`。执行前会动态把：

```python
print(resulted_sql)
```

插入到：

```python
resulted_sql = to_sql(intent_result)
```

下一行，用于把 SQL 结果回收到标准输出。

## Side Effects

- 创建输出目录
- 写出 JSON 与 HTML 文件
- 使用 `requests` 调用本地假的 `/chat/completion` 接口，当前关闭 SSL 校验 `verify=False`
- 在本地配置存在时，可把 `complete_ir` 写入目标项目目录并执行，再把 `stdout/stderr` 回显到页面
- `--serve` 模式下，服务会在内存中维护当前已解析的报告，页面切换文件后会替换当前报告

## Limitations

- 问题文本按字面值精确匹配，不做模糊匹配或同义改写
- 自动发现问题仍基于 `sql_template_match` 的 `query:`；如果日志中存在 `call sqlflow input:`，工具会把它作为主调用边界；跨子线程归因时不再依赖子线程里的 `sql_template_match query`，而是使用子线程日志中的 `MARK QUESTION:` 去匹配主调用里的改写问题链。页面展示的锚点时间、锚点日志和 `match_id` 仍然使用原始命中问题的那条 `sql_template_match`
- 日志中的 15 位数字按线程 ID 处理，不作为单次请求唯一标识；跨子线程场景下，工具会输出主线程 `thread_id`、全部 `associated_thread_ids`，并继续使用主线程上的 `match_id`
- 最终 Prompt 只识别包含 `生成器任务：` 的日志行，并兼容 JSON、Python 对象直接序列化后的单引号消息体，或直接序列化的消息数组；会分别提取前两条 message 的 `content`
- 页面展示的最终 Prompt 是合并结果，但执行时仍使用原始两条消息一起调用，不会直接把合并后的展示文本当请求体
- 页面执行接口和完整 IR 执行接口都按 `match_id` 定位，不再使用线程 ID 直接定位
- 调用结果会额外提取 `verifier result: 0:` 形成 `verifier_failures`，并把出现次数记为 `retry_count`；问题导航只显示时间，但会在成功/失败图标右上角叠加重试次数数字
- `sql_flow exception: SQL is empty` 只用于判定该次调用最终失败；详情区只保留黄色区块展示重试记录
- 兼容字段 `rewritten_question` 现在表示该次主调用的首个 `call sqlflow input:` 内容；完整改写链路看 `rewrite_questions`。子线程是否并入当前调用，则看它的 `MARK QUESTION:` 是否命中这条改写链
- 静态 HTML 适合直接双击打开查看；执行按钮、页面内切换日志文件/目录这类交互能力必须通过 `--serve` 页面使用
- `IR 表定义` 从 `表定义的IR：` 之后开始提取，不保留关键词前缀
- `生成 IR 结果` 从 `最终的IR` 之后开始提取，到 `tables = get_tables_columns(table_exprs)` 为止，并保留结束行
- `完整 IR` 不是直接从日志中提取，而是把 `IR 表定义` 插入 `生成 IR 结果` 中 `@dataclass` 行之前，插入块前后各保留一个空行；`@dataclass` 之前的生成前导内容不会保留到 `complete_ir`
- 执行“完整 IR”时，必须在源码中唯一命中 `resulted_sql = to_sql(intent_result)`；否则接口会拒绝执行

## Status

`temporary`
