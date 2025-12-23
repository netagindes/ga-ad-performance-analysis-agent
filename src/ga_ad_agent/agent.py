from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Literal, Tuple

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from constants import DEFAULT_PROJECT

RuleName = Literal["traffic", "conversion"]

SERVER_SCRIPT_PATH = Path(__file__).with_name("ga_mcp_server.py")


# -------------------------
# Logging setup
# -------------------------
logger = logging.getLogger("ga-kpi-client")


def _setup_logging() -> None:
    """
    Basic console logging. Controlled by LOG_LEVEL env var if you want:
      LOG_LEVEL=DEBUG python client.py
    """
    import os

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = "%(asctime)s %(levelname)s %(name)s - %(message)s"
        handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(handler)

    logger.setLevel(level)


_setup_logging()


# def _tool_result_to_json(result: Any) -> Dict[str, Any]:
#     """
#     Universal MCP ToolResult extraction across SDK versions.
#
#     Strategy:
#     1) If it's pydantic, model_dump() it.
#     2) If it has dict()/to_dict(), use it.
#     3) Else fallback to __dict__.
#     Then look for payload in common places.
#     """
#     import json
#
#     # 1) Convert to a plain python dict (best effort)
#     dumped = None
#
#     if hasattr(result, "model_dump"):
#         dumped = result.model_dump()  # pydantic v2
#     elif hasattr(result, "dict"):
#         dumped = result.dict()  # pydantic v1 style
#     elif hasattr(result, "to_dict"):
#         dumped = result.to_dict()
#     elif hasattr(result, "__dict__"):
#         dumped = dict(result.__dict__)
#     else:
#         dumped = {"repr": repr(result)}
#
#     logger.debug("ToolResult dumped keys=%s", sorted(dumped.keys()))
#
#     # 2) Look for structured content in multiple known locations
#     for key in ("structured_content", "structuredContent", "data", "result", "value", "output"):
#         if key in dumped and dumped[key] is not None:
#             payload = dumped[key]
#             if isinstance(payload, dict):
#                 return payload
#             # sometimes it's already JSON string
#             if isinstance(payload, str):
#                 try:
#                     return json.loads(payload)
#                 except Exception:
#                     return {"raw": payload}
#             return {"raw": payload}
#
#     # 3) Look into content blocks (common schema: {"content":[{"type":"text","text":"..."}]})
#     content = dumped.get("content") or []
#     if isinstance(content, list) and content:
#         # json blocks
#         for part in content:
#             if isinstance(part, dict) and part.get("type") == "json":
#                 payload = part.get("json") or part.get("data")
#                 if isinstance(payload, dict):
#                     return payload
#                 if isinstance(payload, str):
#                     try:
#                         return json.loads(payload)
#                     except Exception:
#                         return {"raw": payload}
#
#         # text blocks
#         texts = []
#         for part in content:
#             if isinstance(part, dict) and part.get("type") == "text":
#                 texts.append(part.get("text", ""))
#             else:
#                 # sometimes it's a class with attrs
#                 if getattr(part, "type", None) == "text":
#                     texts.append(getattr(part, "text", ""))
#
#         joined = "\n".join([t for t in texts if t]).strip()
#         if joined:
#             try:
#                 return json.loads(joined)
#             except Exception:
#                 return {"raw": joined, "isError": dumped.get("isError")}
#
#     # 4) Last resort: return the dumped object so we can see what we're missing
#     return {"tool_result_dump": dumped}


def _tool_result_to_json(result: Any) -> Dict[str, Any]:
    import json

    content = getattr(result, "content", None) or []
    texts = []
    for part in content:
        if getattr(part, "type", None) == "text":
            texts.append(part.text)

    joined = "\n".join(texts).strip()

    logger.info("ToolResult text len=%d head=%r", len(joined), joined[:200])

    if not joined:
        return {"error": "Empty ToolResult.content text", "result_repr": repr(result)}

    try:
        return json.loads(joined)
    except Exception as e:
        return {"error": f"Failed to parse JSON text: {e}", "raw": joined[:2000]}


async def _call_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Spawn the MCP server over stdio, call one tool, return JSON.
    Adds logging around lifecycle + errors.
    """
    logger.info("Calling MCP tool: %s args_keys=%s", tool_name, sorted(args.keys()))
    start = time.time()

    if not SERVER_SCRIPT_PATH.exists():
        raise FileNotFoundError(f"MCP server script not found at {SERVER_SCRIPT_PATH}")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT_PATH)],
        env=None,
    )

    try:
        async with stdio_client(server_params) as (read, write):
            logger.debug("stdio_client started for server script=%s", SERVER_SCRIPT_PATH)
            async with ClientSession(read, write) as session:
                logger.debug("Initializing MCP session...")
                await session.initialize()
                logger.debug("Session initialized. Calling tool=%s", tool_name)

                res = await session.call_tool(tool_name, args)
                out = _tool_result_to_json(res)

                elapsed = time.time() - start
                row_count = out.get("row_count") if isinstance(out, dict) else None

                logger.info(
                    "MCP tool call done: %s elapsed=%.2fs row_count=%s isError=%s",
                    tool_name,
                    elapsed,
                    row_count,
                    getattr(res, "isError", False),
                )
                return out
    except Exception:
        elapsed = time.time() - start
        logger.exception("MCP tool call failed: %s elapsed=%.2fs", tool_name, elapsed)
        raise


def get_month(month: str, dimensions: List[str], project_id: str = DEFAULT_PROJECT) -> Dict[str, Any]:
    logger.info("get_month called: month=%s dimensions=%s project_id=%s", month, dimensions, project_id)
    return asyncio.run(
        _call_tool("get_monthly_data", {"month": month, "dimensions": dimensions, "project_id": project_id})
    )


def get_all(dimensions: List[str], project_id: str = DEFAULT_PROJECT) -> Dict[str, Any]:
    logger.info("get_all called: dimensions=%s project_id=%s", dimensions, project_id)
    return asyncio.run(_call_tool("get_all_data", {"dimensions": dimensions, "project_id": project_id}))


def compare_two_months(
    month_a: str,
    month_b: str,
    dimensions: List[str],
    project_id: str = DEFAULT_PROJECT,
) -> Dict[str, Any]:
    """
    1) Pull KPIs for month A and B for same dimensions
    2) For each segment, compute percent change per KPI
       pct = (b - a) / a * 100 ; if a==0 -> None
    """
    logger.info(
        "compare_two_months called: month_a=%s month_b=%s dimensions=%s project_id=%s",
        month_a,
        month_b,
        dimensions,
        project_id,
    )

    a = get_month(month_a, dimensions, project_id)
    b = get_month(month_b, dimensions, project_id)

    def key(row: Dict[str, Any]) -> Tuple:
        return tuple(row.get(d) for d in dimensions)

    a_rows = a.get("rows", [])
    b_rows = b.get("rows", [])
    logger.info("compare_two_months fetched: month_a_rows=%d month_b_rows=%d", len(a_rows), len(b_rows))

    a_map = {key(r): r for r in a_rows}
    b_map = {key(r): r for r in b_rows}

    all_keys = sorted(set(a_map.keys()) | set(b_map.keys()))
    logger.debug("compare_two_months unique segments=%d", len(all_keys))

    kpis = ["total_visitors", "total_pageviews", "avg_time_on_site_seconds", "total_conversions"]

    out_rows = []
    for k in all_keys:
        ra = a_map.get(k, {})
        rb = b_map.get(k, {})

        segment = {d: k[i] for i, d in enumerate(dimensions)}

        changes = {}
        for metric in kpis:
            av = ra.get(metric, 0) if ra else 0
            bv = rb.get(metric, 0) if rb else 0

            # Handle avg metric being None
            if av is None or bv is None:
                changes[f"{metric}_pct_change"] = None
                continue

            if av == 0:
                changes[f"{metric}_pct_change"] = None
            else:
                changes[f"{metric}_pct_change"] = ((bv - av) / av) * 100.0

        out_rows.append(
            {
                **segment,
                "month_a": month_a,
                "month_b": month_b,
                "a": {m: ra.get(m) for m in kpis},
                "b": {m: rb.get(m) for m in kpis},
                "pct_change": changes,
            }
        )

    logger.info("compare_two_months output rows=%d", len(out_rows))
    return {
        "task": "compare_two_months",
        "dimensions": dimensions,
        "month_a": month_a,
        "month_b": month_b,
        "row_count": len(out_rows),
        "rows": out_rows,
    }


def flagged_segments(
    rule: RuleName,
    project_id: str = DEFAULT_PROJECT,
) -> Dict[str, Any]:
    """
    Requirement:
    - "Given all the dimensions except user country"
    So we use: traffic_source, medium, device_type, page_title
    """
    logger.info("flagged_segments called: rule=%s project_id=%s", rule, project_id)

    dims = ["traffic_source", "medium", "device_type", "page_title"]
    data = get_all(dims, project_id)
    rows = data.get("rows", [])
    logger.info("flagged_segments fetched rows=%d", len(rows))

    flagged = []
    for r in rows:
        pv = r.get("total_pageviews", 0) or 0
        avg_t = r.get("avg_time_on_site_seconds", 0) or 0
        conv = r.get("total_conversions", 0) or 0

        if rule == "traffic":
            if avg_t < 120 and pv < 30:
                flagged.append(r)
        elif rule == "conversion":
            if conv == 0 and pv > 250:
                flagged.append(r)

    logger.info("flagged_segments flagged=%d (rule=%s)", len(flagged), rule)

    return {
        "task": "flagged_segments",
        "rule": rule,
        "dimensions": dims,
        "row_count": len(flagged),
        "rows": flagged,
    }


def conversion_rate_by_country_device(
    month: str,
    project_id: str = DEFAULT_PROJECT,
) -> Dict[str, Any]:
    """
    Requirement:
    - conversion rate = total_conversions / total_visitors
    - for each user country on each device on a given month
    - ordered highest to lowest
    """
    logger.info("conversion_rate_by_country_device called: month=%s project_id=%s", month, project_id)

    dims = ["user_country", "device_type"]
    data = get_month(month, dims, project_id)
    rows = data.get("rows", [])
    logger.info("conversion_rate_by_country_device fetched rows=%d", len(rows))

    out = []
    for r in rows:
        visitors = r.get("total_visitors", 0) or 0
        conv = r.get("total_conversions", 0) or 0
        rate = (conv / visitors) if visitors else 0.0
        out.append(
            {
                "user_country": r.get("user_country"),
                "device_type": r.get("device_type"),
                "total_visitors": visitors,
                "total_conversions": conv,
                "conversion_rate": rate,
                "total_pageviews": r.get("total_pageviews"),
            }
        )

    out.sort(key=lambda x: x["conversion_rate"], reverse=True)
    logger.info("conversion_rate_by_country_device output rows=%d", len(out))

    return {
        "task": "conversion_rate_by_country_device",
        "month": month,
        "dimensions": dims,
        "row_count": len(out),
        "rows": out,
    }
