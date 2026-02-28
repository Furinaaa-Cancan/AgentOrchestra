# IDE Prompt Workflow（Hub 模式）

用一个入口脚本完成交互，不再手工拼事件命令。

## Step 1: Start

```bash
python3 /Volumes/Seagate/Multi-Agent/scripts/ide_hub.py start \
  --task /Volumes/Seagate/Multi-Agent/tasks/examples/task-code-implement.json
```

该命令会：
- 初始化/刷新 session
- 自动生成三端提示词：
  - `/Volumes/Seagate/Multi-Agent/prompts/current-windsurf.txt`
  - `/Volumes/Seagate/Multi-Agent/prompts/current-antigravity.txt`
  - `/Volumes/Seagate/Multi-Agent/prompts/current-codex.txt`
- 指出当前 owner（谁该执行）

## Step 2: 给 owner IDE 粘贴提示词

把 `current-<agent>.txt` 复制到对应 IDE（Claude Opus）。

## Step 3: 提交 IDE 返回结果

```bash
python3 /Volumes/Seagate/Multi-Agent/scripts/ide_hub.py submit \
  --task /Volumes/Seagate/Multi-Agent/tasks/examples/task-code-implement.json \
  --agent windsurf \
  --result-file /path/to/windsurf-output.txt
```

说明：
- `--result-file` 支持纯 JSON 或 markdown 代码块中的 JSON。
- `submit` 会自动推断事件并推进状态（必要时自动补 `builder_start`）。
- 提交后会自动刷新三端提示词，并告诉你下一位 owner。

## Step 4: 查看当前状态（可选）

```bash
python3 /Volumes/Seagate/Multi-Agent/scripts/ide_hub.py status \
  --task /Volumes/Seagate/Multi-Agent/tasks/examples/task-code-implement.json
```
