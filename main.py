"""Read-only access to a local MemOS memory core (memos-local-plugin viewer API).

Single-writer rule: this plugin NEVER writes to MemOS. The host agent that
owns the MemOS bridge (e.g. Hermes) is the only writer; Octop reads traces /
policies / world models / skills via the viewer HTTP API.

Endpoints served by memos-local-plugin (https://github.com/MemTensor/MemOS,
apps/memos-local-plugin):
  GET /api/v1/memory/search     three-tier retrieval (trace/policy/world-model)
  GET /api/v1/memory/trace      one trace by id
  GET /api/v1/memory/policy     one policy by id
  GET /api/v1/memory/world      one world model by id
  GET /api/v1/traces            traces (filter by episodeId etc.)
  GET /api/v1/world-models      recent world models
  GET /api/v1/skills            crystallized skills

NOTE: `memory/search` runs a local embedding pass over the whole memory db;
on large databases it can take well over a minute, so it gets its own long
timeout while the cheap list endpoints stay fast.

Configure via environment:
  MEMOS_API   base URL of the MemOS viewer API (default http://127.0.0.1:18800)
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from octop_harness.plugins import PluginContext

_BASE = os.environ.get("MEMOS_API", "http://127.0.0.1:18800")
_TIMEOUT_FAST = 20.0
_TIMEOUT_SEARCH = 150.0


def _get(path: str, params: dict[str, Any], timeout: float = _TIMEOUT_FAST) -> dict[str, Any]:
    try:
        with httpx.Client(base_url=_BASE, timeout=timeout) as c:
            r = c.get(path, params={k: v for k, v in params.items() if v not in (None, "")})
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:  # noqa: BLE001
        return {"error": f"MemOS bridge unreachable at {_BASE}: {e}"}


def _fmt_hits(data: dict[str, Any]) -> str:
    if "error" in data:
        return json.dumps(data, ensure_ascii=False)
    hits = data.get("hits", [])
    if not hits:
        return "没有命中任何记忆。"
    lines = []
    for h in hits:
        tier = h.get("tier")
        kind = h.get("refKind", "?")
        rid = h.get("refId", "")
        score = h.get("score")
        snippet = (h.get("snippet") or "").replace("\n", " ")[:300]
        lines.append(f"[T{tier} {kind} {rid} score={score}] {snippet}")
    return "\n".join(lines)


async def memos_search(query: str, top: int = 5) -> str:
    """三层检索 MemOS 长期记忆：L1 trace(对话轨迹)、L2 policy(策略)、L3 world model(环境模型)。"""
    data = _get(
        "/api/v1/memory/search",
        {"q": query[:512], "top": max(1, min(top, 20))},
        timeout=_TIMEOUT_SEARCH,
    )
    out = _fmt_hits(data)
    if isinstance(data, dict) and data.get("injectedContext"):
        out += "\n\n--- 注入上下文 ---\n" + str(data["injectedContext"])[:2000]
    return out


async def memos_get(id: str, kind: str = "trace") -> str:
    """按 id 取一条记忆全文。kind: trace | policy | world_model。id 形如 tr_xxx / po_xxx / wm_xxx。"""
    path = {
        "trace": "/api/v1/memory/trace",
        "policy": "/api/v1/memory/policy",
        "world_model": "/api/v1/memory/world",
    }.get(kind, "/api/v1/memory/trace")
    data = _get(path, {"id": id})
    return json.dumps(data, ensure_ascii=False)[:6000]


async def memos_timeline(episode_id: str, limit: int = 20) -> str:
    """按 episode id 取一个 episode 的逐步轨迹（step-by-step traces）。"""
    data = _get("/api/v1/traces", {"episodeId": episode_id, "limit": limit})
    if "error" in data:
        return json.dumps(data, ensure_ascii=False)[:2000]
    items = data.get("traces") or data
    return json.dumps(items, ensure_ascii=False)[:6000]


async def memos_environment(limit: int = 5) -> str:
    """查 L3 环境模型（world models）：结构事实、行为规则、项目约束。返回最近条目列表。"""
    data = _get("/api/v1/world-models", {"limit": limit})
    return json.dumps(data, ensure_ascii=False)[:6000]


async def memos_skill_list(status: str = "", limit: int = 10) -> str:
    """列出已结晶的 skill（可调用记忆技能）。status 可选: candidate | active | archived。"""
    data = _get("/api/v1/skills", {"status": status, "limit": limit})
    return json.dumps(data, ensure_ascii=False)[:6000]


def setup(ctx: PluginContext) -> None:
    ctx.tool(
        "memos_search",
        memos_search,
        description=(
            "三层检索 MemOS 长期记忆（对话轨迹 trace / 策略 policy / 环境模型 world model）。"
            "参数 query 为自然语言关键词（2-5 个关键词），top 为每层返回条数（默认 5）。"
            "返回带 tier/refId/score 的命中摘要。只读；大库上检索可能耗时 1-2 分钟，耐心等待。"
        ),
    )
    ctx.tool(
        "memos_get",
        memos_get,
        description=(
            "按 id 读取一条 MemOS 记忆的完整内容。参数 id 形如 tr_xxx/po_xxx/wm_xxx（来自 memos_search 结果），"
            "kind 为 trace|policy|world_model（默认 trace）。只读，秒级返回。"
        ),
    )
    ctx.tool(
        "memos_timeline",
        memos_timeline,
        description="按 episode id 读取该 episode 的逐步执行轨迹。参数 episode_id、limit（默认 20）。只读，秒级返回。",
    )
    ctx.tool(
        "memos_environment",
        memos_environment,
        description=(
            "查询 MemOS L3 环境模型（world models）：机器拓扑、行为规则、项目约束等沉淀知识。"
            "返回最近条目列表，limit 默认 5。只读，秒级返回。关键词查询请用 memos_search。"
        ),
    )
    ctx.tool(
        "memos_skill_list",
        memos_skill_list,
        description=(
            "列出 MemOS 已结晶的 skill。参数 status 可选 candidate|active|archived（空=全部），limit 默认 10。只读，秒级返回。"
        ),
    )
