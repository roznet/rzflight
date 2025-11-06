#!/usr/bin/env python3
# Place this file at: euro_aip/web/server/chat/ask.py  (or .../api/chat/ask.py)
# Deps:
#   pip install langchain langchain-core langchain-openai langchain-mcp-adapters pydantic fastapi
# Env:
#   OPENAI_API_KEY=sk-...
#   (optional) OPENAI_MODEL=gpt-4o
#   (optional) MCP_BASE_URL=https://mcp.flyfun.aero/euro_aip
#   (optional) MCP_AUTH_HEADER=Authorization
#   (optional) MCP_AUTH_TOKEN=Bearer xxx

from __future__ import annotations

import os
import asyncio
import logging
import traceback
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# LangChain / MCP
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)

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

# ------------------------------------
# Lazy, global initialization (warm)
# ------------------------------------
_mcp_client: Optional[MultiServerMCPClient] = None
_agent = None
_init_lock = asyncio.Lock()

async def _get_agent():
    """
    Lazily initialize and memoize the Agent that uses OpenAI tool-calling
    and MCP tools via langchain-mcp-adapters.
    """
    global _mcp_client, _agent
    if _agent:
        return _agent

    async with _init_lock:
        if _agent:
            return _agent

        # 1) Build the MCP client using official langchain-mcp-adapters
        # According to docs: https://docs.langchain.com/oss/python/langchain/mcp
        server_config = {
            "euro_aip": {
                "transport": "streamable_http",
                "url": MCP_RPC_URL,
            }
        }
        # Add auth headers if provided (check if MultiServerMCPClient supports this)
        if _auth_token:
            # Note: MultiServerMCPClient may need headers in server config
            # Check langchain-mcp-adapters docs for exact format
            server_config["euro_aip"]["headers"] = {_auth_header: _auth_token}
        
        try:
            _mcp_client = MultiServerMCPClient(server_config)
            # Get all tools from MCP server
            all_tools = await _mcp_client.get_tools()
        except Exception as e:
            error_msg = f"MCP server not reachable at {MCP_RPC_URL}"
            logger.error(f"{error_msg}: {type(e).__name__}: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=502,
                detail=f"{error_msg}. Please check the MCP server is running and accessible."
            )

        # 2) Filter tools by allowlist if configured
        if _TOOL_ALLOWLIST:
            tools = [t for t in all_tools if t.name in _TOOL_ALLOWLIST]
        else:
            tools = all_tools
        
        if not tools:
            error_msg = f"No MCP tools available. Allowlist: {list(_TOOL_ALLOWLIST)}"
            logger.error(error_msg)
            raise HTTPException(
                status_code=500,
                detail="No MCP tools available for the agent. Check tool allowlist configuration."
            )

        # 3) Create agent with filtered tools
        try:
            agent = create_agent(
                model=OPENAI_MODEL,
                tools=tools,
                system_prompt=SYSTEM_PROMPT,
            )
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            logger.error(f"Failed to create agent: {error_type}: {error_msg}", exc_info=True)
            
            if "API key" in error_msg or "authentication" in error_msg.lower():
                raise HTTPException(
                    status_code=500,
                    detail="OpenAI API authentication failed. Please check OPENAI_API_KEY environment variable."
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to create agent: {error_type}. Check logs for details."
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
    try:
        agent = await _get_agent()
    except HTTPException:
        # Re-raise HTTP exceptions (like 502 Bad Gateway)
        raise
    except Exception as e:
        logger.error(f"Failed to initialize agent: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize chat agent. Please try again later."
        )
    
    try:
        messages = [m.model_dump() for m in (req.chat_history or [])]
        messages.append({"role": "user", "content": req.input})
        result = await agent.ainvoke({"messages": messages})
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        logger.error(f"Agent invocation failed: {error_type}: {error_msg}", exc_info=True)
        
        # Provide user-friendly error messages based on error type
        if "API key" in error_msg or "authentication" in error_msg.lower():
            raise HTTPException(
                status_code=500,
                detail="OpenAI API authentication failed. Please check API key configuration."
            )
        elif "rate limit" in error_msg.lower() or "429" in error_msg:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Please try again in a moment. Error: {error_msg}"
            )
        elif "timeout" in error_msg.lower():
            raise HTTPException(
                status_code=504,
                detail="Request timed out. The MCP server may be slow or unresponsive."
            )
        else:
            # Generic error for unexpected issues
            raise HTTPException(
                status_code=500,
                detail="An error occurred while processing your request. Please try again."
            )

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
        except Exception as e:
            logger.warning(f"Failed to extract text from agent response: {e}")
            return str(res)

    try:
        return AskResponse(text=_extract_text(result))
    except Exception as e:
        logger.error(f"Failed to format response: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to format agent response. Please try again."
        )

@router.get("/health")
async def chat_health():
    """
    Lightweight health check (verifies MCP reachability the first time).
    """
    try:
        await _get_agent()
        return {"ok": True, "mcp": MCP_BASE_URL, "model": OPENAI_MODEL}
    except HTTPException as e:
        # Re-raise HTTP exceptions with their status codes
        raise
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        logger.error(f"Health check failed: {error_type}: {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {error_type}. Check logs for details."
        )