# MyGO v0.8.1 二次严格评审报告

> 审查焦点：边界条件、并发安全、错误处理路径、数据完整性
> 审查日期：2026-03-07（第二轮）

---

## 评审总结

| 等级 | 数量 | 说明 |
|------|------|------|
| High | 1 | 影响功能正确性 |
| Medium | 3 | 影响健壮性/可靠性 |
| Low | 2 | 代码质量 |

**相比第一轮**：核心链路已修复，本轮发现的问题更多是边界条件和防御性编程。

---

## High (1)

### R2-H1: `build_node` 超时检查逻辑有时间窗口问题

**文件**: `graph.py` line 440-453

```python
build_started = time.time()
ref_time = state.get("build_started_at") or state.get("started_at", 0)
if not ref_time:
    ref_time = build_started
timeout = state.get("timeout_sec", 1800)
if ref_time and timeout:
    elapsed = time.time() - ref_time
```

**问题**: `build_started_at` 在 plan_node 中被重置为 `None`（line 331），所以首次进入 build_node 时 `ref_time` 总是 fallback 到 `started_at`（plan 完成时间）。但 `interrupt()` 可能暂停数分钟甚至数小时。当 `resume` 恢复时，`time.time() - started_at` 包含了**用户思考时间**，可能误判超时。

实际上这是**设计正确**的 — `started_at` 记录的是 plan 分配时刻，timeout 应该包含等待时间。但如果用户希望 timeout 只计算 IDE 实际执行时间（从 `my done` 提交开始），这个逻辑就不对。

**影响**: 长时间不操作后提交可能被误判超时。有 `_check_total_timeout` 的 2 小时兜底保护。

**建议**: 在文档中明确 timeout 语义（包含等待时间 vs 仅执行时间）。如需改为仅执行时间，可在 resume 返回后再取 `time.time()` 作为 ref_time。

---

## Medium (3)

### R2-M1: `root_dir()` 使用 `@lru_cache` 但 CWD 可能在运行时改变

**文件**: `config.py` line 51-53

```python
@lru_cache(maxsize=1)
def root_dir() -> Path:
    return _find_root()
```

**问题**: `_find_root()` 基于 `Path.cwd()` 向上搜索。一旦缓存，即使 CWD 变化也不会重新计算。对于 `my dashboard` 这样的长期运行进程，如果用户在另一个目录启动，缓存的路径不会更新。

**影响**: 低 — CLI 命令通常在目标目录启动。但 `my dashboard` 通过环境变量传递路径给 Node.js 后端，绕过了这个问题。

### R2-M2: `EventHooks` 不是线程安全的

**文件**: `graph_infra.py` line 245-288

```python
class EventHooks:
    def on_node_enter(self, node, callback):
        self._enter.setdefault(node, []).append(callback)  # 无锁

    def fire_enter(self, node, state):
        for cb in self._enter.get(node, []):  # 无锁迭代
```

**问题**: `_enter`/`_exit`/`_error` 字典的读写没有锁保护。虽然 CPython GIL 在单纯 dict 操作上提供了一定安全性，但 `fire_*` 遍历列表时如果另一个线程同时调用 `on_node_*` 添加回调，可能导致 `RuntimeError: dictionary changed size during iteration`。

**影响**: 在 `--decompose` 并行模式下，多个线程同时运行图节点时理论上可能触发。但实践中 hooks 在启动时一次性注册完毕，运行时不会再修改，所以**当前使用模式安全**。

**建议**: 加 `threading.Lock` 或在 `fire_*` 中用 `list(self._enter.get(node, []))` 做快照。

### R2-M3: `trace.py` 中 `append_trace_event` 在 Windows 上没有文件锁

**文件**: `trace.py` line 58-59

```python
if fcntl is not None:
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
```

**问题**: `fcntl` 是 POSIX-only。Windows 上 `fcntl` 为 `None`，trace 事件追加没有任何并发保护。如果多个进程同时写同一个 `.events.jsonl`，可能交错写入导致 JSON 行损坏。

**影响**: 仅 Windows 平台。macOS/Linux 正确。README 已标注 macOS 全支持。

---

## Low (2)

### R2-L1: `_decide_reject_retry` 没有传入 `original_convo` 参数

**文件**: `graph.py` 的 `decide_node` line 862

```python
else:
    result = _decide_reject_retry(state, reviewer_output)
```

对比 `_decide_request_changes` 调用时传了 `original_convo=original_convo`，但 `_decide_reject_retry` 的 dashboard 写入直接用 `state.get("conversation", [])`，在 trim 场景下仍是 trimmed 版本。

**建议**: 给 `_decide_reject_retry` 也传入 `original_convo`，与 request_changes 路径一致。

### R2-L2: `watcher.py` 在 `check_once` 中每次检测都 `import hashlib`

**文件**: `watcher.py` line 102

```python
import hashlib
content_hash = hashlib.sha256(raw.encode()).hexdigest()
```

热路径上的函数级 import。虽然 Python 会缓存已导入的模块，开销极小，但风格上应移到文件顶部。

---

## 链路完整性验证（第二轮）

| 检查项 | 状态 | 说明 |
|--------|------|------|
| Plan → Build 状态传递 | ✅ | builder_id, reviewer_id, started_at 正确传递 |
| Build interrupt → resume 数据完整性 | ✅ | result 经过验证+enrichment 后传给 review |
| Review → Decide 决策路由 | ✅ | approve/reject/request_changes 三路完整 |
| Retry 循环 feedback 传递 | ✅ | 结构化反馈包含 quality gate warnings |
| Conversation trim 不丢关键信息 | ✅ | 保留 head 5 + tail N + summary + all feedback |
| Cancel 检测 TOCTOU 安全 | ✅ | 直接 open 无 exists 检查 |
| Lock acquire 原子性 | ✅ | O_CREAT\|O_EXCL + 自愈 |
| Outbox polling 幂等性 | ✅ | SHA256 content-hash 去重 |
| CLI agent 进程管理 | ✅ | timeout + kill + zombie reap |
| Git hooks 配置缓存 | ✅ | 闭包工厂模式（本轮修复） |
| Web SSE 新事件检测 | ✅ | byte-offset seek（本轮修复） |
| Snapshot 路径遍历防护 | ✅ | sanitize task_id/node_name |
| Trace 文件并发写入 | ⚠️ | POSIX 有 flock，Windows 无保护 |
| EventHooks 线程安全 | ⚠️ | 当前使用模式安全，理论风险存在 |

---

## 总结

**核心链路健壮**。经过两轮评审 + 修复，Plan→Build→Review→Decide 循环、文件系统通信、并发控制、Web Dashboard 数据流均验证通过。

本轮发现的问题集中在：
- 超时语义需要文档明确（R2-H1）
- 线程安全理论风险但当前使用安全（R2-M2）
- Windows 平台兼容性（R2-M3）
- dashboard 显示一致性小修补（R2-L1）

**建议修复**: R2-L1（1 行改动）。其余记录即可，暂不修复。
