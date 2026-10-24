# octop-memos-plugin

[中文](#中文说明) | [English](#english)

A read-only **Octop** plugin that exposes the local **MemOS** memory core
([MemTensor/MemOS · memos-local-plugin](https://github.com/MemTensor/MemOS/tree/main/apps/memos-local-plugin))
as five agent tools: three-tier retrieval, item fetch, episode timeline,
world models, and crystallized skills.

Octop 只读插件：把本机 MemOS（memos-local-plugin）的长期记忆以 5 个工具暴露给
Octop agent —— 三层检索、按 id 取全文、episode 轨迹、环境模型、结晶 skill。

> **Read-only by design.** The agent that owns the MemOS bridge (e.g. Hermes)
> stays the single writer; this plugin never writes to MemOS, so there is no
> dual-write conflict.
> 设计上纯只读：MemOS 的写入仍由宿主 agent（如 Hermes）单写者负责，本插件不写。

## Tools / 工具

| Tool | Endpoint | Notes |
|---|---|---|
| `memos_search(query, top)` | `GET /api/v1/memory/search` | L1 trace / L2 policy / L3 world-model hybrid retrieval. On large databases the local embedding pass may take 1–2 min (plugin timeout: 150 s). |
| `memos_get(id, kind)` | `GET /api/v1/memory/{trace,policy,world}` | `id` like `tr_xxx` / `po_xxx` / `wm_xxx`. |
| `memos_timeline(episode_id, limit)` | `GET /api/v1/traces?episodeId=` | Step-by-step traces of one episode. |
| `memos_environment(limit)` | `GET /api/v1/world-models` | Recent world models (topology, rules, constraints). |
| `memos_skill_list(status, limit)` | `GET /api/v1/skills` | Crystallized skills; status = candidate/active/archived. |

## Prerequisites / 前提

1. **MemOS** with the local plugin's viewer/API running (default port:
   Hermes `18800`, OpenClaw `18799`). See the upstream repo for setup.
2. **Octop** ≥ a build with the plugin system (`octop plugin install`).

If the MemOS viewer has password protection enabled, either disable it
(localhost-only deployment) or front it with a session-terminating proxy;
this plugin speaks plain HTTP without login.

## Install / 安装

```bash
# from a local checkout
octop plugin install /path/to/octop-memos-plugin

# live-reload without restarting octop run:
curl -X POST -H "Authorization: Bearer <admin-jwt>" http://127.0.0.1:8088/api/plugins/reload
```

Verify: `octop plugin list` shows `memos-memory ... [loaded]`, or
`GET /api/plugins` shows `"loaded": true`.

## Configuration / 配置

| Env var | Default | Meaning |
|---|---|---|
| `MEMOS_API` | `http://127.0.0.1:18800` | Base URL of the MemOS viewer API. |

Set it in the environment before launching `octop run`, e.g.
`MEMOS_API=http://127.0.0.1:18799 octop run` for an OpenClaw-owned bridge.

## Chinese / 中文说明

本插件让 Octop 的 agent 只读访问本机 MemOS 记忆库：

- `memos_search`：三层混合检索（对话轨迹 / 策略 / 环境模型），返回带
  tier/refId/score 的命中摘要。大库上冷检索可能耗时 1–2 分钟。
- `memos_get`：按 `tr_/po_/wm_` 前缀 id 取单条记忆全文。
- `memos_timeline`：按 episode id 回放逐步执行轨迹。
- `memos_environment`：列出最近的 L3 环境模型。
- `memos_skill_list`：列出已结晶 skill（candidate/active/archived）。

安装：`octop plugin install <本目录>`，然后在管理端或
`POST /api/plugins/reload` 热加载。MemOS API 地址用环境变量 `MEMOS_API`
覆盖（默认 `http://127.0.0.1:18800`）。若 MemOS viewer 开了密码保护，请先
关闭（仅限本机部署）或加一层免登录代理——本插件不做登录。

## Compatibility / 兼容性

- Written against memos-local-plugin **v2.x** HTTP API (`/api/v1/*`).
- The plugin system targets Octop's `octop_harness.plugins.PluginContext`
  (`kind: tool`). If upstream changes the manifest schema, adjust
  `plugin.yaml` accordingly.

## License

Apache-2.0 (matches upstream MemOS).
