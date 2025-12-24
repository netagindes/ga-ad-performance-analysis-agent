from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple
import re
import calendar
import logging
import time
import json

from google.cloud import bigquery
from mcp.server.fastmcp import FastMCP

from constants import DEFAULT_PROJECT, DATASET, TABLE_WILDCARD, DIMENSIONS, KPI_FIELDS


# -------------------------
# Logging setup
# -------------------------
logger = logging.getLogger("ga-kpi-server")


def _setup_logging() -> None:
    """
    Basic console logging. Controlled by LOG_LEVEL env var if you want:
      LOG_LEVEL=DEBUG python ga_mcp_server.py
    """
    import os

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    # Avoid duplicate handlers if this module is imported/reloaded
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = "%(asctime)s %(levelname)s %(name)s - %(message)s"
        handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(handler)

    logger.setLevel(level)


_setup_logging()

mcp = FastMCP("ga-kpi-server")

DimensionLiteral = Literal["traffic_source", "user_country", "medium", "device_type", "page_title"]


def _validate_dimensions(dimensions: List[str]) -> List[str]:
    logger.debug("Validating dimensions: %s", dimensions)
    if not dimensions:
        logger.error("Validation failed: dimensions list is empty")
        raise ValueError("dimensions must be a non-empty list")

    unknown = [d for d in dimensions if d not in DIMENSIONS.keys()]
    if unknown:
        logger.error("Validation failed: unknown dimensions=%s allowed=%s", unknown, sorted(DIMENSIONS.keys()))
        raise ValueError(f"Unknown dimensions: {unknown}. Allowed: {sorted(DIMENSIONS.keys())}")

    seen = set()
    out = []
    for d in dimensions:
        if d not in seen:
            out.append(d)
            seen.add(d)

    logger.debug("Validated dimensions (deduped): %s", out)
    return out


def _month_to_suffix_range(month: str) -> Tuple[str, str]:
    logger.debug("Parsing month to suffix range: month=%s", month)
    m = re.fullmatch(r"(\d{4})-(\d{2})", month)
    if not m:
        logger.error("Invalid month format: %s", month)
        raise ValueError("month must be in 'YYYY-MM' format, e.g. '2017-08'")

    y = int(m.group(1))
    mo = int(m.group(2))
    if not (1 <= mo <= 12):
        logger.error("Invalid month value: %s (MM out of range)", month)
        raise ValueError("month must have MM between 01 and 12")

    last_day = calendar.monthrange(y, mo)[1]
    start = f"{y:04d}{mo:02d}01"
    end = f"{y:04d}{mo:02d}{last_day:02d}"
    logger.info("Month %s -> suffix range %s..%s", month, start, end)
    return start, end


def _build_query(
    dimensions: List[str],
    suffix_start: Optional[str],
    suffix_end: Optional[str],
) -> Tuple[str, List[bigquery.ScalarQueryParameter]]:
    logger.info(
        "Building query: dimensions=%s suffix_start=%s suffix_end=%s",
        dimensions,
        suffix_start,
        suffix_end,
    )
    dims = _validate_dimensions(dimensions)

    select_dims = ",\n        ".join([f"{DIMENSIONS[d]} AS {d}" for d in dims])
    dim_names = ", ".join(dims)

    where_suffix = ""
    params: List[bigquery.ScalarQueryParameter] = []
    if suffix_start and suffix_end:
        where_suffix = "AND _TABLE_SUFFIX BETWEEN @suffix_start AND @suffix_end"
        params.append(bigquery.ScalarQueryParameter("suffix_start", "STRING", suffix_start))
        params.append(bigquery.ScalarQueryParameter("suffix_end", "STRING", suffix_end))

    query = f"""
    -- 1) sessions: one row per session (safe for timeOnSite / transactions)
    WITH sessions AS (
      SELECT
        fullVisitorId,
        visitId,
        totals.timeOnSite AS timeOnSite,
        totals.transactions AS transactions
      FROM `{TABLE_WILDCARD}`
      WHERE
        trafficSource.source IS NOT NULL
        AND trafficSource.medium IS NOT NULL
        AND totals.visits >= 1
        {where_suffix}
    ),

    -- 2) pageviews_hits: one row per PAGE hit (safe for pageviews)
    pageviews_hits AS (
      SELECT
        fullVisitorId,
        visitId,
        {select_dims}
      FROM `{TABLE_WILDCARD}`,
      UNNEST(hits) AS hits
      WHERE
        trafficSource.source IS NOT NULL
        AND trafficSource.source != '(not set)'
        AND trafficSource.medium IS NOT NULL
        AND trafficSource.medium NOT IN ('(not set)', '(none)')
        AND totals.visits >= 1
        AND hits.type = 'PAGE'
        {where_suffix}
    ),

    -- 3) session_dims: dedupe to one row per (session, segment) so session KPIs aren't multiplied
    session_dims AS (
      SELECT DISTINCT
        fullVisitorId,
        visitId,
        {dim_names}
      FROM pageviews_hits
    ),

    -- 4) aggregate pageviews at hit grain
    pageviews_agg AS (
      SELECT
        {dim_names},
        COUNT(1) AS total_pageviews
      FROM pageviews_hits
      GROUP BY {dim_names}
    ),

    -- 5) aggregate session KPIs at (session, segment) grain
    sessions_agg AS (
      SELECT
        d.{dim_names},
        COUNT(DISTINCT d.fullVisitorId) AS total_visitors,
        AVG(s.timeOnSite) AS avg_time_on_site_seconds,
        COUNT(DISTINCT IF(s.transactions >= 1,
          CONCAT(CAST(d.fullVisitorId AS STRING), "-", CAST(d.visitId AS STRING)),
          NULL
        )) AS total_conversions
      FROM session_dims d
      JOIN sessions s
      USING (fullVisitorId, visitId)
      GROUP BY d.{dim_names}
    )

    -- 6) combine
    SELECT
      s.{dim_names},
      s.total_visitors,
      p.total_pageviews,
      s.avg_time_on_site_seconds,
      s.total_conversions
    FROM sessions_agg s
    JOIN pageviews_agg p
    USING ({dim_names})
    WHERE p.total_pageviews >= 20
    ORDER BY p.total_pageviews DESC
    """

    logger.debug("Query built. Params=%s", [(p.name, p.type_, p.value) for p in params])
    # If you want the SQL text at DEBUG level:
    logger.debug("Query SQL:\n%s", query)
    return query, params


def _run_bq(query: str, params: List[bigquery.ScalarQueryParameter], project_id: str) -> List[Dict[str, Any]]:
    logger.info("Running BigQuery job: project_id=%s params=%s", project_id, [p.name for p in params])
    logger.debug("Query SQL:\n%s", query)
    start = time.time()

    try:
        client = bigquery.Client(project=project_id)
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        job = client.query(query, job_config=job_config)

        logger.info("BigQuery job submitted: job_id=%s location=%s", job.job_id, job.location)
        rows = job.result()  # waits

        data = [dict(r) for r in rows]
        elapsed = time.time() - start
        logger.info("BigQuery job done: job_id=%s rows=%d elapsed=%.2fs", job.job_id, len(data), elapsed)
        return data

    except Exception:
        elapsed = time.time() - start
        logger.exception("BigQuery query failed after %.2fs", elapsed)
        raise


@mcp.tool()
def get_monthly_data(
    month: str,
    dimensions: List[DimensionLiteral],
    project_id: str = DEFAULT_PROJECT,
) -> str:
    suffix_start, suffix_end = _month_to_suffix_range(month)
    query, params = _build_query(dimensions=list(dimensions), suffix_start=suffix_start, suffix_end=suffix_end)
    data = _run_bq(query, params, project_id=project_id)

    resp = {
        "scope": "month",
        "month": month,
        "dimensions": list(dimensions),
        "kpis": KPI_FIELDS,
        "row_count": len(data),
        "rows": data,
        "notes": {
            "source": f"`{DATASET}.ga_sessions_*` (public sample dataset)",
            "table_suffix_filter": {"start": suffix_start, "end": suffix_end},
            "having": "total_pageviews >= 20",
        },
    }

    logger.info("Tool get_monthly_data returning: row_count=%d", resp["row_count"])
    return json.dumps(resp)  # <-- IMPORTANT: return text JSON


@mcp.tool()
def get_all_data(
    dimensions: List[DimensionLiteral],
    project_id: str = DEFAULT_PROJECT,
) -> str:
    query, params = _build_query(dimensions=list(dimensions), suffix_start=None, suffix_end=None)
    data = _run_bq(query, params, project_id=project_id)

    resp = {
        "scope": "all",
        "dimensions": list(dimensions),
        "kpis": KPI_FIELDS,
        "row_count": len(data),
        "rows": data,
        "notes": {
            "source": f"`{DATASET}.ga_sessions_*` (public sample dataset)",
            "having": "total_pageviews >= 20",
        },
    }

    logger.info("Tool get_all_data returning: row_count=%d", resp["row_count"])
    return json.dumps(resp)  # <-- IMPORTANT


def main():
    logger.info("Running MCP server...")
    mcp.run()


if __name__ == "__main__":
    main()
