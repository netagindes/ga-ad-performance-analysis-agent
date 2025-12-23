# Ad Performance Analysis Agent 
┌─----───────────┐
│ User (part 4)  │
│    Dashboard   │
└─────┬----──────┘
      │ structured query
      ▼
┌──────────────────────┐
│   Agent (Part 3)     │
│  - Reasoning         │
│  - Business rules    │
│  - KPI logic         │
└─────┬────────────────┘
      │ calls tool via adapter
      ▼
┌──────────────────────┐
│     mcp_client       │
│  (Client Adapter)    │
└─────┬────────────────┘
      │ MCP tool request
      ▼
┌──────────────────────┐
│  MCP Server (Part 2) │
│  - get_monthly_data  │
│  - get_all_data      │
└─────┬────────────────┘
      │ SQL execution
      ▼
┌──────────────────────┐
│   BigQuery (Part 1)  │
│ (Public GA Dataset)  │
└──────────────────────┘

## Step by Step Guide:
[1] Make sure you add the following to your environment (you can use the attached .env file):
    - OPENAI_API_KEY
    - GOOGLE_CLOUD_PROJECT_ID
[Optional] Run configuration check by running the config file.

[2] Connect to your GCP account:
```bash
gcloud auth login
gcloud auth application-default login
```

[3] Run Ad Performance Analysis Agent

If you will use your local environment, and run the Streamlit Dashboard with the following command.

```bash
pip install -r requirements.txt
streamlit run src/agent_app.py
```

[Optional] If you chose to use the Dockerfile - Note that it references an earlier (less fine) version and needs to be fixed before running.
  - [Optional] run command:
```bash
docker compose up --build
docker compose up --force-recreate
```
  - Open Streamlit dashboard: [Ad Performances Analysis Agent](http://localhost:8502)

If you want access to my GCP project, please contact me.

## Project Setups

**Personal GCP Project**
```
    Name: "Ad Performance Analysis Agent"
    ID: "ad-performance-analysis-agent"
```
**Repo URL**
## Input Dataset

`bigquery-public-data.google_analytics_sample.ga_sessions_*`

* Public BigQuery dataset.

* The format and schema of the Google Analytics data that is imported into BigQuery - [Documentation](https://support.google.com/analytics/answer/3437719?hl=en)


[**Google Analytics Sample**](https://console.cloud.google.com/marketplace/product/obfuscated-ga360-data/obfuscated-ga360-data) - Twelve months (August 2016 to August 2017) of obfuscated Google Analytics 360 data from the [Google Merchandise Store](https://merch.google/)

### Part 1 - Data Preparation and Exploration

**Monthly data querying:**

Direct extraction from the BigQuery public data


- [Bigquery Query](https://console.cloud.google.com/bigquery?ws=!1m7!1m6!12m5!1m3!1sad-performance-analysis-agent!2sus-central1!3s36bf4fb0-e3dd-4f2e-9d4e-4915ba6a40c4!2e1)

- Bigquery Table ID: `ad-performance-analysis-agent.ga_sessions_data.data`

```sql
CREATE OR REPLACE TABLE `ga_sessions_data.data`

PARTITION BY month AS
SELECT
  DATE_TRUNC(PARSE_DATE('%Y%m%d', _TABLE_SUFFIX), MONTH) AS month,  -- The first day of the month.
  
  -- Grouping Dimensions
  NULLIF(trafficSource.source, '(not set)') AS traffic_source,
  NULLIF(geoNetwork.country, '(not set)') AS user_country,
  NULLIF(NULLIF(trafficSource.medium, '(not set)'), '(none)') AS medium,
  device.deviceCategory AS device_type,  -- ENUM: "PAGE", "TRANSACTION", "ITEM", "EVENT", "SOCIAL", "APPVIEW", "EXCEPTION"
  hits.page.pageTitle AS page_title,
  
  -- Key Metrics Aggregation
  COUNT(DISTINCT fullVisitorId) AS total_visitors,
  SUM(CASE WHEN hits.type = 'PAGE' THEN 1 ELSE 0 END) AS total_pageviews,
  AVG(totals.timeOnSite) AS avg_time_on_site_seconds,
  SUM(CASE WHEN totals.transactions >= 1 THEN 1 ELSE 0 END) AS total_conversions

FROM
  `bigquery-public-data.google_analytics_sample.ga_sessions_*`,
  UNNEST(hits) AS hits -- Unnest the hits array to analyze page-level data

WHERE
  trafficSource.source IS NOT NULL
  AND trafficSource.medium IS NOT NULL
  AND totals.visits >= 1 -- Filter out non-meaningful sessions

GROUP BY
  -- session_date,
  month,
  traffic_source,
  medium,
  device_type,
  user_country,
  page_title

HAVING
  total_pageviews >= 20 -- Ensure enough volume per page/channel combo

```

### Part 2 - Building the MCP Server

#### Tools
1. `get_monthly_data`: This tool should accept a month and a set of requested dimension columns and return a structured **JSON response** containing the calculated KPIs for these dimensions on this month (as described in the query above).

2. `get_all_data`: This tool should accept a set of requested dimension columns and return a structured **JSON response** containing the calculated KPIs for these dimensions on all the data.


### Part 3 - Building the Agent

#### Flagging Rules:

* **Traffic rule:** Avg. time on site < 120 seconds and total pageviews below 30
* **Conversion rule:** zero conversions and more than 250 pageviews

#### Agent Abilities:

1. *Compare between two months* what were the changes to the KPIs for all the dimensions requested by the user. Provide for each segment the percentage change in each KPI.

2. Given all the dimensions except user country, and a rule name (traffic or conversion) return all the *flagged segments*.

3. Return the *conversion rate* (total conversions / total visitors) for each user country on each device on a given month, ordered from highest to lowest.


### Part 4 - Building the Client Interaction
Build an AI Agent application that interacts with the MCP created in Part 2.

* Streamlit
* Dashboard
