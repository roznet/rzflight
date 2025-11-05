#!/usr/bin/env python3
# Place this file at: euro_aip/web/server/chat/ask.py  (or .../api/chat/ask.py)
# Deps:
#   pip install langchain langchain-core langchain-openai langchain-community httpx pydantic fastapi
# Env:
#   OPENAI_API_KEY=sk-...
#   (optional) OPENAI_MODEL=gpt-4o
#   (optional) MCP_BASE_URL=https://mcp.flyfun.aero
#   (optional) MCP_AUTH_HEADER=Authorization
#   (optional) MCP_AUTH_TOKEN=Bearer xxx

from __future__ import annotations

import os
import asyncio
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, create_model

# LangChain / OpenAI
from langchain_openai import ChatOpenAI
from langchain_core.tools import StructuredTool
from langchain.agents import create_agent

router = APIRouter(prefix="/chat", tags=["chat"])

SYSTEM_PROMPT = (
    "You are an assistant specialized in European GA/IFR/VFR operations. "
    "Prefer tools for factual data (AIP entries, rules, border crossing, procedures, airports near a route). "
    "Return concise, practical answers. Use ICAO identifiers and ISO-2 country codes where relevant."
)

# -----------------------
# Config via environment
# -----------------------
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
MCP_BASE_URL = os.getenv("MCP_BASE_URL", "https://mcp.flyfun.aero/euro_aip").rstrip("/")
MCP_RPC_URL = os.getenv("MCP_RPC_URL") or f"{MCP_BASE_URL}"

_auth_header = os.getenv("MCP_AUTH_HEADER") or "Authorization"
_auth_token = os.getenv("MCP_AUTH_TOKEN") or ""
MCP_HEADERS: Dict[str, str] = {}
if _auth_token:
    MCP_HEADERS[_auth_header] = _auth_token

# --------------------------------
# Simple async client for HTTPS MCP (JSON-RPC)
# --------------------------------
class MCPClientHTTP:
    def __init__(self, rpc_url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 60.0):
        self.rpc_url = rpc_url
        self.client = httpx.AsyncClient(timeout=timeout, headers=headers or {})
        self._initialized = False
        self._next_id = 1

    async def _rpc(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": method,
        }
        self._next_id += 1
        if params is not None:
            payload["params"] = params
        r = await self.client.post(self.rpc_url, json=payload)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("error"):
            raise RuntimeError(f"MCP error calling {method}: {data['error']}")
        # Standard JSON-RPC result envelope
        return data.get("result", data)

    async def _ensure_initialized(self):
        if self._initialized:
            return
        # Minimal initialize per spec; servers may ignore unsupported capabilities
        try:
            await self._rpc(
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                    "clientInfo": {"name": "euro_aip_web", "version": "0.1.0"},
                },
            )
        except Exception:
            # Some servers allow direct calls without explicit initialize; continue
            pass
        else:
            # Best-effort notification
            try:
                await self._rpc("notifications/initialized")
            except Exception:
                pass
        self._initialized = True

    async def list_tools(self) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        res = await self._rpc("tools/list")
        # Accept either {"tools": [...]} or a bare list
        if isinstance(res, dict) and "tools" in res:
            return res["tools"]
        if isinstance(res, list):
            return res
        raise RuntimeError(f"Unexpected tools/list response: {res}")

    async def call_tool(self, name: str, args: Dict[str, Any]) -> Any:
        await self._ensure_initialized()
        res = await self._rpc("tools/call", {"name": name, "arguments": args})
        # Accept either {"content": ...} or a bare value
        return res

# ------------------------------------
# Lazy, global initialization (warm)
# ------------------------------------
_mcp: Optional[MCPClientHTTP] = None
_agent = None
_init_lock = asyncio.Lock()

# Optional: restrict which MCP tools are exposable to the agent
_TOOL_ALLOWLIST = {
    "search_airports",
    "get_airport_details",
    "find_airports_near_route",
    "list_rules_for_country",
    "compare_rules_between_countries",
    "list_rule_categories_and_tags",
    "list_rule_countries",
    "get_border_crossing_airports",
    "get_airport_statistics",
}

async def _mcp_tools_as_langchain_tools(mcp: MCPClientHTTP) -> List[StructuredTool]:
    tools = []
    for t in await mcp.list_tools():
        name = t.get("name")
        if _TOOL_ALLOWLIST and name not in _TOOL_ALLOWLIST:
            continue

        schema = t.get("parameters_json_schema") or {}
        props = schema.get("properties", {}) or {}
        reqd = set(schema.get("required", []) or [])

        # Build a Pydantic args model that mirrors the MCP JSON Schema
        fields = {k: (Any, ... if k in reqd else None) for k in props.keys()}
        ArgsModel = create_model(f"{name}_Args", **fields)

        async def _acall(**kwargs):
            # Important: closure captures 'name'
            return await mcp.call_tool(name, kwargs)

        tools.append(
            StructuredTool.from_function(
                name=name,
                description=t.get("description", ""),
                args_schema=ArgsModel,
                coroutine=_acall,  # async call, no threadpool
            )
        )
    return tools

async def _get_agent():
    """
    Lazily initialize and memoize the Agent that uses OpenAI tool-calling
    and your HTTPS MCP tools.
    """
    global _mcp, _agent
    if _agent:
        return _agent

    async with _init_lock:
        if _agent:
            return _agent

        # 1) Build the MCP client and sanity-check connectivity
        _mcp = MCPClientHTTP(MCP_RPC_URL, headers=MCP_HEADERS)
        try:
            await _mcp.list_tools()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"MCP not reachable: {e}")

        # 2) Build LLM + tools + agent
        llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0)
        tools = await _mcp_tools_as_langchain_tools(_mcp)
        if not tools:
            raise HTTPException(status_code=500, detail="No MCP tools exposed to the agent (allowlist empty?)")

        agent = create_agent(
            model=OPENAI_MODEL,  # v1 accepts a model id string
            tools=tools,
            system_prompt=SYSTEM_PROMPT,
        )
        _agent = agent
        return _agent

# ---------------
# API models
# ---------------
class ChatMsg(BaseModel):
    role: str
    content: str

class AskRequest(BaseModel):
    input: str
    chat_history: Optional[List[ChatMsg]] = None

class AskResponse(BaseModel):
    text: str

# ---------------
# Endpoints
# ---------------
@router.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest) -> AskResponse:
    """
    Chat endpoint that lets the model use your aviation MCP tools when helpful.
    """
    agent = await _get_agent()
    messages = [m.model_dump() for m in (req.chat_history or [])]
    messages.append({"role": "user", "content": req.input})
    result = await agent.ainvoke({"messages": messages})

    def _extract_text(res: Any) -> str:
        try:
            if isinstance(res, dict) and "messages" in res and res["messages"]:
                last = res["messages"][-1]
                content = last.get("content") if isinstance(last, dict) else getattr(last, "content", None)
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text" and "text" in block:
                            return block["text"]
                    return "".join(str(block) for block in content)
                if content is not None:
                    return str(content)
            if isinstance(res, str):
                return res
            return str(res)
        except Exception:
            return str(res)

    return AskResponse(text=_extract_text(result))

@router.get("/health")
async def chat_health():
    """
    Lightweight health check (verifies MCP reachability the first time).
    """
    try:
        await _get_agent()
        return {"ok": True, "mcp": MCP_BASE_URL, "model": OPENAI_MODEL}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))