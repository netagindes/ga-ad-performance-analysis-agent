from typing import cast

import pandas as pd
import streamlit as st

from src.constants import DEFAULT_PROJECT, DIMENSION_KEYS, DIMENSIONS
from src.ga_ad_agent.agent import (
    RuleName,
    compare_two_months,
    conversion_rate_by_country_device,
    get_all,
    get_month,
    flagged_segments,
    run_adk_agent,
)


st.set_page_config(page_title="GA Agent", layout="wide")
st.title("GA Ad Performance Analysis Agent")  # (using Google ADK + FastMCP Server
st.caption("Requests go through the ADK agent first, then execute via MCP tools.")

# project_id = st.text_input("Billing Project ID", value=DEFAULT_PROJECT)
project_id = DEFAULT_PROJECT


def _log_mcp_tool(tool_name: str):
    """Flow-visualizer style log for MCP tool execution."""
    st.info(f"Agent used MCP tool: {tool_name}")


def _render_compare(r, dimensions):
    rows = r.get("rows", [])
    flat = []
    for row in rows:
        base = {d: row.get(d) for d in dimensions}
        pct = row.get("pct_change", {})
        flat.append({**base, **pct})
    df = pd.DataFrame(flat)
    st.dataframe(df, use_container_width=True)
    st.json(r)


def _render_flagged(r):
    df = pd.DataFrame(r.get("rows", []))
    st.dataframe(df, use_container_width=True)
    st.json(r)


def _render_conversion(r):
    df = pd.DataFrame(r.get("rows", []))
    st.dataframe(df, use_container_width=True)
    st.json(r)


def _render_kpis(r):
    """Generic renderer for raw KPI outputs."""
    df = pd.DataFrame(r.get("rows", []))
    st.dataframe(df, use_container_width=True)
    st.json(r)


st.subheader("Ask the LLM Agent Controller")
default_prompt = f"""
Compare August 2016 to July 2017 by device_type and traffic_source. \n
Identify the flagged segments by medium dimension, using traffic/ conversion rule. \n
Calculate the conversion rate by country & device type for the month of 01-2017.
"""
user_prompt = st.text_area("Describe what you want to analyze", value=default_prompt)

if st.button("Run agent", type="primary"):
    with st.spinner("Running ADK agent..."):
        agent_out = run_adk_agent(user_prompt)

    st.write("Agent output (parsed + raw):")
    st.json(agent_out)

    if agent_out.get("error"):
        st.error(agent_out["error"])
        if agent_out.get("model"):
            st.info(f"Model used: {agent_out['model']} (set GEMINI_MODEL to override)")
        st.stop()

    action = agent_out.get("action")
    args = agent_out.get("arguments") or {}

    if not action:
        st.error("Agent did not return an action. Please refine your request.")
    else:
        st.success(f"Agent chose action: {action}")
        with st.spinner("Executing selected action..."):
            try:
                if action == "compare_two_months":
                    _log_mcp_tool("get_monthly_data")
                    month_a = args.get("month_a")
                    month_b = args.get("month_b")
                    dims = args.get("dimensions") or DIMENSIONS
                    if not (month_a and month_b):
                        raise ValueError("compare_two_months requires month_a and month_b")
                    res = compare_two_months(month_a, month_b, dims, project_id=project_id)
                    _render_compare(res, dims)
                elif action == "identify_flagged_segments":
                    _log_mcp_tool("get_all_data")
                    rule = cast(RuleName, args.get("rule", "traffic"))
                    res = flagged_segments(rule, project_id=project_id)
                    _render_flagged(res)
                elif action == "conversion_rate_by_country_and_device":
                    _log_mcp_tool("get_monthly_data")
                    month = args.get("month") or args.get("month_a") or args.get("month_b")
                    if not month:
                        raise ValueError("conversion_rate_by_country_and_device requires month")
                    res = conversion_rate_by_country_device(month, project_id=project_id)
                    _render_conversion(res)
                elif action == "get_monthly_data":
                    _log_mcp_tool("get_monthly_data")
                    month = args.get("month")
                    dims = args.get("dimensions") or DIMENSION_KEYS
                    if not month:
                        raise ValueError("get_monthly_data requires month (YYYY-MM)")
                    res = get_month(month, dims, project_id=project_id)
                    _render_kpis(res)
                elif action == "get_all_data":
                    _log_mcp_tool("get_all_data")
                    dims = args.get("dimensions") or DIMENSION_KEYS
                    res = get_all(dims, project_id=project_id)
                    _render_kpis(res)
                else:
                    st.error(f"Unsupported action returned by agent: {action}")
            except Exception as exc:
                st.error(f"Failed to execute action: {exc}")

st.divider()
st.subheader("Use Logical Controls (Agent Tools)")

task = st.selectbox(
    "Direct tool run",
    [
        "Compare two months (% change per KPI)",
        "Flag segments by rule (traffic/conversion)",
        "Conversion rate by country × device (month)",
    ],
)

if task == "Compare two months (% change per KPI)":
    colA, colB = st.columns(2)
    with colA:
        month_a = st.text_input("Month A (YYYY-MM)", value="2017-07")
    with colB:
        month_b = st.text_input("Month B (YYYY-MM)", value="2016-08")

    dims = st.multiselect("Dimensions", DIMENSION_KEYS, default=DIMENSIONS)

    if st.button("Run comparison (manual)"):
        _log_mcp_tool("get_monthly_data")
        res = compare_two_months(month_a, month_b, dims, project_id=project_id)
        _render_compare(res, dims)

elif task == "Flag segments by rule (traffic/conversion)":
    rule = cast(RuleName, st.selectbox("Rule", ["traffic", "conversion"]))
    if st.button("Run flagging (manual)"):
        _log_mcp_tool("get_all_data")
        res = flagged_segments(rule, project_id=project_id)
        _render_flagged(res)

else:
    month = st.text_input("Month (YYYY-MM)", value="2017-08")
    if st.button("Compute conversion rates (manual)"):
        _log_mcp_tool("get_monthly_data")
        res = conversion_rate_by_country_device(month, project_id=project_id)
        _render_conversion(res)
