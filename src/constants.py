# constants.py
from __future__ import annotations

import os
from typing import Dict, List

# ---- BigQuery config ----
DEFAULT_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "ad-performance-analysis-agent")

# Public dataset lives under bigquery-public-data project.
# Keep DEFAULT_PROJECT for billing/quota.
DATASET: str = "bigquery-public-data.google_analytics_sample"
TABLE_WILDCARD: str = f"{DATASET}.ga_sessions_*"

# Allowlist of dimensions exposed to clients
DIMENSIONS: Dict[str, str] = {
    "traffic_source": "trafficSource.source",
    # Treat "(not set)" as NULL so downstream filters/aggregations behave as expected
    "user_country": "NULLIF(geoNetwork.country, '(not set)')",
    "medium": "trafficSource.medium",
    "device_type": "device.deviceCategory",
    "page_title": "hits.page.pageTitle",
}

# For Streamlit UI dropdowns / type hints (keep same order everywhere)
DIMENSION_KEYS: List[str] = list(DIMENSIONS.keys())

# KPIs returned by tools
KPI_FIELDS: List[str] = [
    "total_visitors",
    "total_pageviews",
    "avg_time_on_site_seconds",
    "total_conversions",
]
