import streamlit as st
import pandas as pd

from constants import DEFAULT_PROJECT, DIMENSION_KEYS, DIMENSIONS
from ga_ad_agent.agent import (
    compare_two_months,
    flagged_segments,
    conversion_rate_by_country_device,
)

st.set_page_config(page_title="GA Agent", layout="wide")
st.title("GA Agent (via MCP)")

task = st.selectbox(
    "Task",
    [
        "Compare two months (% change per KPI)",
        "Flag segments by rule (traffic/conversion)",
        "Conversion rate by country × device (month)",
    ],
)

# project_id = st.text_input("Billing Project ID", value=DEFAULT_PROJECT)
project_id = DEFAULT_PROJECT

st.divider()

if task == "Compare two months (% change per KPI)":
    colA, colB = st.columns(2)
    with colA:
        month_a = st.text_input("Month A (YYYY-MM)", value="2017-07")
    with colB:
        month_b = st.text_input("Month B (YYYY-MM)", value="2016-08")

    dims = st.multiselect("Dimensions", DIMENSION_KEYS, default=DIMENSIONS)

    if st.button("Run comparison"):
        res = compare_two_months(month_a, month_b, dims, project_id=project_id)
        rows = res["rows"]

        # Flatten for display: show pct_change columns + segment columns
        flat = []
        for r in rows:
            base = {d: r.get(d) for d in dims}
            pct = r.get("pct_change", {})
            flat.append({**base, **pct})

        df = pd.DataFrame(flat)
        st.dataframe(df, use_container_width=True)
        st.json(res)

elif task == "Flag segments by rule (traffic/conversion)":
    rule = st.selectbox("Rule", ["traffic", "conversion"])
    if st.button("Run flagging"):
        res = flagged_segments(rule, project_id=project_id)
        df = pd.DataFrame(res["rows"])
        st.dataframe(df, use_container_width=True)
        st.json(res)

else:
    month = st.text_input("Month (YYYY-MM)", value="2017-08")
    if st.button("Compute conversion rates"):
        res = conversion_rate_by_country_device(month, project_id=project_id)
        df = pd.DataFrame(res["rows"])
        st.dataframe(df, use_container_width=True)
        st.json(res)
