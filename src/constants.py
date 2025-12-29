from typing import Dict, List

from src import config as cfg


# Keep DEFAULT_PROJECT for billing/quota.
DEFAULT_PROJECT: str = cfg.GOOGLE_CLOUD_PROJECT

# Public dataset lives under bigquery-public-data project. Date-sharing dataset.
# [Google Analytics Sample](
# https://console.cloud.google.com/marketplace/product/obfuscated-ga360-data/obfuscated-ga360-data)
DATASET: str = "bigquery-public-data.google_analytics_sample"
TABLE_WILDCARD: str = f"{DATASET}.ga_sessions_*"

# Allowlist of dimensions (segments) exposed to clients
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

# KPIs (Key Metrics Aggregation)
KPI_FIELDS: List[str] = [
    "total_visitors",
    "total_pageviews",
    "avg_time_on_site_seconds",
    "total_conversions",
]
