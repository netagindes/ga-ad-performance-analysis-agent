import asyncio
import json
import logging
import re
import sys
import time
import uuid
from typing import Any, Dict, List, Literal, Tuple

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams

from src import config as cfg
from src.constants import DEFAULT_PROJECT, DIMENSION_KEYS, KPI_FIELDS

RuleName = Literal["traffic", "conversion"]

SERVER_SCRIPT_PATH = cfg.PROJECT_ROOT / "src/ga_ad_agent/ga_mcp_server.py"

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

    call_tool_server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT_PATH)],
        env=None,
    )

    try:
        async with stdio_client(call_tool_server_params) as (read, write):
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


# @tool("compare_two_months_tool")
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

        changes: dict[str, float | None] = {}
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
        dimensions: list[str] | None = None,
        project_id: str = DEFAULT_PROJECT,
) -> Dict[str, Any]:
    """
    Requirement:
    - "Given all the dimensions except user country"
    So we use: traffic_source, medium, device_type, page_title
    """
    logger.info("flagged_segments called: rule=%s project_id=%s", rule, project_id)

    allowed_dims = [d for d in DIMENSION_KEYS if d != "user_country"]
    raw_dims = dimensions or allowed_dims

    seen = set()
    dims: list[str] = []
    for d in raw_dims:
        if d not in allowed_dims:
            raise ValueError(f"Invalid dimension for flagged_segments: {d}. Allowed: {allowed_dims}")
        if d not in seen:
            dims.append(d)
            seen.add(d)

    if not dims:
        raise ValueError("flagged_segments requires at least one dimension")

    if rule == "traffic":
        rule_kpis = ["total_visitors", "total_conversions"]
        enforcement_metrics = ["avg_time_on_site_seconds", "total_pageviews"]

        def _rule_ok(m: Dict[str, Any]) -> bool:
            return m["avg_time_on_site_seconds"] < 120 and m["total_pageviews"] < 30
    elif rule == "conversion":
        rule_kpis = ["total_visitors", "avg_time_on_site_seconds"]
        enforcement_metrics = ["total_conversions", "total_pageviews"]

        def _rule_ok(m: Dict[str, Any]) -> bool:
            return m["total_conversions"] == 0 and m["total_pageviews"] > 250
    else:
        raise ValueError(f"Unknown rule: {rule}")

    kpi_keys = list(dict.fromkeys(rule_kpis + enforcement_metrics))

    data = get_all(dims, project_id)
    rows = data.get("rows", [])
    logger.info("flagged_segments fetched rows=%d", len(rows))

    flagged = []
    for r in rows:
        # New block - start
        metrics = {
            "total_pageviews": r.get("total_pageviews", 0) or 0,
            "avg_time_on_site_seconds": r.get("avg_time_on_site_seconds", 0) or 0,
            "total_conversions": r.get("total_conversions", 0) or 0,
            "total_visitors": r.get("total_visitors", 0) or 0,
        }

        if _rule_ok(metrics):
            out_row = {d: r.get(d) for d in dims}
            for k in kpi_keys:
                out_row[k] = metrics.get(k)
            flagged.append(out_row)
            # New block - end

    logger.info("flagged_segments flagged=%d (rule=%s)", len(flagged), rule)

    return {
        "task": "flagged_segments",
        "rule": rule,
        "dimensions": dims,
        "kpis": kpi_keys,
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


def compare_two_months_tool(
        month_a: str,
        month_b: str,
        dimensions: list[str],
        project_id: str = DEFAULT_PROJECT,
):
    """Compare KPIs between two months using MCP-backed helper."""
    res = compare_two_months(month_a, month_b, dimensions, project_id=project_id)
    return res.get("rows", [])


def identify_flagged_segments(
        rule: RuleName,
        dimensions: list[str] | None = None,
        project_id: str = DEFAULT_PROJECT,
):
    """Return flagged segments based on traffic or conversion rule."""
    res = flagged_segments(rule, dimensions=dimensions, project_id=project_id)
    return res


def calculate_conversion_rate_by_country_and_device(
        month: str,
        project_id: str = DEFAULT_PROJECT,
):
    """Return conversion rate by country and device."""
    res = conversion_rate_by_country_device(month, project_id=project_id)
    return res.get("rows", [])


# Wrap functions as ADK FunctionTool instances
compare_months_tool = FunctionTool(compare_two_months_tool)
flagged_segments_tool = FunctionTool(identify_flagged_segments)
conversion_rate_by_country_device_tool = FunctionTool(calculate_conversion_rate_by_country_and_device)


server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT_PATH)],
        env=None,
    )

toolset = McpToolset(
        connection_params=StdioConnectionParams(server_params=server_params),
        tool_filter=["get_monthly_data", "get_all_data"],
    )

# Model selection: allow override via GEMINI_MODEL.
# Use a v1beta-available model by default to avoid 404s on older endpoints.
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"

LLM_AGENT_DESCRIPTION = f""" 
Agent to answer questions about Google Analytics data stored in BigQuery public dataset `bigquery-public-data.google_analytics_sample.ga_sessions_*`.
Uses: 
    - MCP tools (get_monthly_data/get_all_data) via MCP Server
    - deterministic function tools (compare_two_months/flagged_segments/conversion_rate_by_country_device) 
        that implement your assignment abilities. 
Prefer deterministic results."""

LLM_AGENT_INSTRUCTIONS = f"""
You are a Google Analytics agent that must respond with a JSON action + arguments and ground answers in tool outputs.

**Use only these action names:**
1) get_monthly_data: fetch KPIs for a month.
    - Inputs: month (YYYY-MM), dimensions (subset of {DIMENSION_KEYS}).
2) get_all_data: fetch KPIs across all months.
    - Inputs: dimensions (subset of {DIMENSION_KEYS}).
3) compare_two_months: compare KPIs between two months for given dimensions (optional).
    - Dimensions default to all: traffic_source, user_country, medium, device_type, page_title.
    - Compute % change per KPI per segment.
4) identify_flagged_segments: apply a rule (traffic | conversion) across all data (exclude user_country).
    - Inputs: rule=traffic|conversion; dimensions optional subset of [traffic_source, medium, device_type, page_title] (defaults to all four).
    - traffic rule: avg_time_on_site_seconds < 120 AND total_pageviews < 30
    - conversion rule: total_conversions = 0 AND total_pageviews > 250
5) conversion_rate_by_country_and_device: compute conversion rate per (user_country, device_type) for a month.
    - Inputs: month (YYYY-MM). Drop rows with zeros for total_visitors and total_conversions. conversion_rate = total_conversions / total_visitors.

**Important context:**
- Dataset: `bigquery-public-data.google_analytics_sample.ga_sessions_*` (Aug 2016–Aug 2017). Keep month within this range.
- Only use dimensions from: {DIMENSION_KEYS}
- Only use KPIs: {KPI_FIELDS}
- Preserve user month format (YYYY-MM or YYYY-MM-01); the literal "all_data" means full history.

**Always return JSON with keys:** action, arguments.
"""

agent = LlmAgent(
    name="ad_performance_agent",
    description=LLM_AGENT_DESCRIPTION.strip(),
    instruction=LLM_AGENT_INSTRUCTIONS.strip(),
    # """
    # Use tools when needed.
    # You can do exactly these actions (choose one):
    # 1) compare_two_months: Compare KPIs between two months for requested dimensions and report % changes.
    # 2) identify_flagged_segments: Given dimensions (excluding user_country) and a rule name (traffic|conversion), 
    #    return flagged segments.
    # 3) conversion_rate_by_country_and_device: For a timeframe, return conversion rate per (user_country, device_type), 
    #    ordered high->low. 
    #    Use a month when specified, or use "all_data" when the user asks for all history—do not force a month.
    #    conversion rate = (total_conversions / total_visitors) for the given timeframe

    # When selecting dimensions, only use these known fields:
    # traffic_source, medium, device_type, user_country, page_title.
    # Months are provided as YYYY-MM or YYYY-MM-01 depending on the user's format; preserve what the user uses. 
    # If the user wants all history, keep the literal value "all_data".
    # Return JSON only with keys: action, arguments.
    # """
    model=DEFAULT_GEMINI_MODEL,
    tools=[compare_months_tool, flagged_segments_tool, conversion_rate_by_country_device_tool, toolset]
)


def _extract_text_from_event(event: Any) -> str | None:
    """
    Pull plain text from an ADK event content if present.
    """
    content = getattr(event, "content", None)
    parts = getattr(content, "parts", None) if content else None
    if not parts:
        return None

    texts = []
    for part in parts:
        text = getattr(part, "text", None)
        if text:
            texts.append(text)

    joined = "\n".join(texts).strip()
    return joined or None


def _strip_code_fences(text: str) -> str:
    """
    Remove surrounding Markdown code fences such as ```json ... ``` if present.
    Keeps inner content unchanged.
    """
    stripped = text.strip()
    fence = re.compile(r"^```[a-zA-Z0-9_-]*\n(?P<body>.*)\n```$", re.DOTALL)
    match = fence.match(stripped)
    if match:
        return match.group("body").strip()
    return stripped


def _parse_agent_json(text: str) -> Dict[str, Any]:
    """
    Try to parse JSON from model text. Falls back to {}
    """
    cleaned = _strip_code_fences(text)
    if not cleaned.strip():
        raise ValueError(f"Empty text passed to _parse_agent_json(): {text!r}")

    try:
        return json.loads(cleaned)
    except Exception as e:
        logger.info("Failed to parse JSON directly: %s text_head=%r", e, cleaned[:200])
        pass

    # Heuristic: grab first {...}
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = cleaned[start: end + 1]
        try:
            return json.loads(snippet)
        except Exception as e:
            logger.error(f"ValueError: Failed to parse JSON: {e}")
            return {}

    return {}


def run_adk_agent(
        user_message: str,
        *,
        user_id: str = "streamlit-user",
        session_id: str | None = None,
) -> Dict[str, Any]:
    """
    Run the ADK agent once and return parsed action/arguments plus raw text.
    This is used by the Streamlit UI as the first processing step.
    """

    # # Basic env guard - fail fast with a useful error in UI.
    # has_google_key = bool(os.getenv("GOOGLE_API_KEY"))
    # has_vertex = bool(os.getenv("GOOGLE_CLOUD_PROJECT")) #and os.getenv("VERTEXAI_LOCATION"))
    # if not (has_google_key or has_vertex):
    #     return {
    #         "error": "Missing credentials: set GOOGLE_API_KEY, or VERTEXAI_PROJECT and VERTEXAI_LOCATION.",
    #         "raw_text": None,
    #         "event_count": 0,
    #     }

    runner = InMemoryRunner(agent=agent, app_name="ad_performance_agent")

    async def _run():
        async_events = await runner.run_debug(
            user_messages=user_message,
            user_id=user_id,
            session_id=session_id or f"session-{uuid.uuid4()}",
            quiet=True,
            verbose=False,
        )
        await runner.close()
        return async_events

    try:
        events = asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001
        return {
            "error": f"ADK agent failed: {exc}",
            "model": DEFAULT_GEMINI_MODEL,
            "raw_text": None,
            "event_count": 0,
        }

    response_text = None
    for event in events:
        response_text = _extract_text_from_event(event) or response_text

    try:
        parsed = _parse_agent_json(response_text or "")
    except ValueError as e:
        logger.error(f"ValueError: empty response text: {e}")
        
        return {
            "error": f"Empty Response passed to JSON parser: {e}",
            "model": DEFAULT_GEMINI_MODEL,
            "raw_text": response_text,
            "event_count": len(events),
        }
    # New block - start
    except Exception as e:
        logger.exception("Unexpected JSON parse error: %s", e)
        return {
            "error": f"Failed to parse agent JSON: {e}",
            "model": DEFAULT_GEMINI_MODEL,
            "raw_text": response_text,
            "event_count": len(events),
        }
        # New block - end

    return {
        "action": parsed.get("action"),
        "arguments": parsed.get("arguments", {}) if isinstance(parsed, dict) else {},
        "raw_text": response_text,
        "event_count": len(events),
    }
