# MyGO v0.8.1 系统链路严格评审报告

> 审查范围：graph.py, orchestrator.py, cli.py, cli_watch.py, workspace.py, driver.py, git_ops.py, web/app.js, web/server.py, web/static/index.html
> 审查日期：2026-03-07

---

## 评审总结

| 等级 | 数量 | 说明 |
|------|------|------|
| Critical | 1 | 可能导致数据丢失或系统故障 |
| High | 3 | 重要逻辑缺陷，影响可靠性 |
| Medium | 4 | 设计改进，影响健壮性 |
| Low | 3 | 代码质量/可维护性 |

---

## Critical (1)

### C1: SSE 新事件检测逻辑不准确 (app.js)

**文件**: `web/app.js` line 248-251

```javascript
const prevCount = Math.max(0, prevSize > 0 ? allEvents.length - 5 : 0);
const newEvents = allEvents.slice(prevCount);
```

**问题**: 每次 trace 文件变化时，整个文件被重新解析 (`parseJsonlFile`)，然后用 `allEvents.length - 5` 估算新事件起始位置。这个 `-5` 是硬编码的魔法数字，会导致：
- 重复推送已发送的事件（如果新增 < 5 条）
- 漏掉事件（如果一次写入 > 5 条）
- 内存浪费（每次都解析整个文件）

**对比**: Python `server.py` 的 `_collect_changes()` 使用 `fh.seek(prev_size)` 只读新增部分，逻辑正确。

**修复建议**: 用 `prevSize` 换算行数，或像 Python 版一样 seek 到上次位置只读新内容。

---

## High (3)

### H1: `_on_build_submit` 每次调用都重新加载 Git 配置

**文件**: `git_ops.py` line 316-318

```python
def _on_build_submit(state, result=None):
    cfg = load_git_config()  # 每次都读磁盘 + 解析 YAML
```

**问题**: `_on_build_submit` 和 `_on_decide_approve` 每次被调用都执行 `load_git_config()`，涉及磁盘读取和 YAML 解析。虽然单次开销不大，但在高频 retry 场景下是无谓消耗。

**修复建议**: 在 `register_git_hooks()` 时读取一次配置并通过闭包传入。

### H2: `_process_outbox` 中 resume 失败后未检查下一状态

**文件**: `cli_watch.py` line 191-206

```python
try:
    with _resume_lock:
        next_status = resume_task(app, task_id, data)
except Exception as e:
    ...
    return "return"

if not next_status.is_terminal and next_status.waiting_role:
    _show_next_agent(next_status, ts, ...)
break  # ← 这里 break 了，但没处理 next_status.is_terminal 的情况
```

**问题**: `break` 后回到 `_run_watch_loop` 的 `while True`，下一个循环会通过 `get_task_status` 检测到 terminal 状态并处理。所以功能上没问题，但存在一个循环周期的延迟（2 秒）。在任务被 approve 的场景下，用户会多等 2 秒才看到完成消息。

**影响**: 用户体验，非数据问题。可在 break 前加 terminal 检查来消除延迟。

### H3: Web Dashboard 无认证保护

**文件**: `web/app.js` 全局, `web/server.py` 全局

**问题**: Dashboard 没有任何认证机制。虽然默认绑定 `127.0.0.1`，CLI 也有 non-localhost 警告，但：
- 任何能访问该端口的进程都能读取任务数据
- `api/tasks/{id}` 可以读取所有任务的 YAML 内容（可能含敏感需求）
- SSE 流可以被任意客户端订阅

**风险**: 低（仅本地运行时），但如果用户用 `--host 0.0.0.0` 暴露到网络则为高风险。

**修复建议**: 
- 在 `--host 0.0.0.0` 时生成随机 token，通过 URL 参数或 cookie 验证
- 或在 CLI 警告中更强调风险

---

## Medium (4)

### M1: `decide_node` 中 state 被浅拷贝后与原始 conversation 不一致

**文件**: `graph.py` line 833-835

```python
trimmed = trim_conversation(original_convo)
if len(trimmed) < len(original_convo):
    state = {**state, "conversation": trimmed}
```

**问题**: `state` 被替换为浅拷贝的 dict，但 `_decide_request_changes` 和 `_decide_reject_retry` 仍然通过 `state.get("conversation", [])` 获取 **trimmed** 版本来写 dashboard。这意味着 dashboard 显示的对话历史可能不完整。

**已有缓解**: `original_convo` 被正确传递给 `_decide_request_changes` 用于计数，但 dashboard 写入用的是 trimmed 版本。

### M2: Node.js app.js 没有 graceful shutdown

**文件**: `web/app.js`

**问题**: 没有处理 SIGTERM/SIGINT 信号。当 CLI 通过 `subprocess.run` 启动 Node.js 后，Ctrl-C 可能不会正确关闭 chokidar watchers 和 HTTP 连接。

**修复建议**: 添加 `process.on('SIGTERM', ...)` 关闭 server 和 watcher。

### M3: Python server.py 的 SSE 是 async 但其他端点是 sync

**文件**: `web/server.py` line 145 vs line 49-61

`api_events` 是 `async def`（正确，因为用了 `await asyncio.sleep`），但 `index()`、`api_status()`、`api_tasks()` 是普通 `def`。这本身不是 bug（FastAPI 会把同步函数放到线程池），但风格不一致。

### M4: `listTasks()` 在 Node.js 中对每个文件调用两次 `stat()`

**文件**: `web/app.js` line 121-143

```javascript
const files = fs.readdirSync(tasksDir)
  .filter(...)
  .map(f => {
    const stat = fs.statSync(fp);           // 第一次 stat
    return { name: f, path: fp, mtime: stat.mtimeMs / 1000 };
  })
```

然后 `listTasks` 外层没有第二次 stat，但 Python `server.py` line 91 每个文件调用了两次 `stat()`：

```python
for f in sorted(..., key=lambda p: p.stat().st_mtime, ...):  # stat 1
    ...
    "modified": f.stat().st_mtime,  # stat 2
```

**影响**: 21 个任务 × 2 次 stat = 42 次系统调用，性能可优化。

---

## Low (3)

### L1: `_is_cancelled` 每次都 `import yaml`

**文件**: `graph.py` line 879

```python
def _is_cancelled(task_id: str) -> bool:
    import yaml
```

函数级 import 在热路径上有微小开销。`yaml` 已在模块顶部被其他文件导入过，可移到顶部。

### L2: Web Dashboard `event-count` 的 `data-i18n="event_count_zero"` 会被动态覆盖

当有事件到来时，JS 会用 `tf('events_count', n)` 覆盖 `event-count` 的内容，但 `data-i18n` 属性仍然是 `event_count_zero`。下次切换语言时 `applyLang()` 会把它重置为 "0 events" / "0 个事件"，丢失实际计数。

**修复建议**: 在 `addTimelineEvent` 中更新后移除 `data-i18n` 属性，或在 `applyLang` 中跳过已有动态内容的元素。

### L3: `app.js` 的 `SAFE_TASK_ID_RE` 与 `server.py` 的正则相同但独立维护

两个后端维护了相同的验证逻辑，未来修改时容易不同步。

---

## 链路完整性验证

| 链路环节 | 状态 | 说明 |
|----------|------|------|
| CLI → compile_graph | ✅ | 正确编译，SQLite checkpoint 持久化 |
| Plan → 写 inbox/TASK.md | ✅ | 角色正确，prompt 渲染完整 |
| Build → interrupt → 等待 | ✅ | 暂停/恢复机制正确 |
| Watch → 检测 outbox → resume | ✅ | 轮询+验证+锁保护 |
| Review → interrupt → 等待 | ✅ | 同 Build |
| Decide → 路由 (approve/reject/retry) | ✅ | 逻辑完整，含 rubber-stamp 检测 |
| retry → Plan (带 feedback) | ✅ | 结构化反馈 + DDI decay 警告 |
| Git hooks (build/approve/plan) | ✅ | 正确检查 final_status |
| Lock 管理 (acquire/release) | ✅ | 原子 O_EXCL + 自愈 |
| Web Dashboard → API → 文件系统 | ✅ | 两套后端都正确读取 |
| SSE → 文件变化 → 推送 | ⚠️ | Node.js 版事件计数有 C1 问题 |
| i18n 中英文切换 | ⚠️ | L2: 动态覆盖 vs data-i18n 冲突 |
| Task 分解 (--decompose) | ✅ | 拓扑排序 + 并行 + 隔离目录 |
| 超时保护 (per-node + total) | ✅ | 双层超时检查 |
| Cancel 检测 | ✅ | TOCTOU 安全 |

---

## 建议优先级

1. **立即修复**: C1 (SSE 事件重复) + L2 (i18n 动态覆盖冲突)
2. **建议修复**: H1 (Git config 缓存) + M2 (graceful shutdown)
3. **可选改进**: M1, M4, L1, L3
4. **暂不处理**: H2 (2秒延迟，用户无感知), H3 (默认本地运行), M3 (风格不一致)
