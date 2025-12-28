# Ad Performance Analysis Agent 

![MCP + ADK Agent Structure](image.png)

## Preliminary Setups

This code uses:
* GCP project for BigQuery and Google ADK
* Gemini API for Agent construction

You are going to use **your own GCP project** and needs to:
* Login to the project and extract the project ID: 
  - Open [your project's homepage](https://console.cloud.google.com/welcome/new) - make sure this is the project you want to use.
  - Refresh and copy the website URL to extract the project's id from the project query param:
  `https://console.cloud.google.com/welcome/new?project=your-google-project-id` 
  --> 
      GOOGLE_PROJECT_ID='your-google-project-id'
  **NOTE:** Make sure to use this value throughout google cli project setup and environment variable setups.

 * Generate a Google API Key
  - Generate a Google API key for the project via the [Your GCP Project > APIs & Services > Credentials](https://console.cloud.google.com/apis/credentials?project=your-google-project-id)
  - Press `show key`, copy the value and save it:
      GOOGLE_API_KEY='YOUR_GOOGLE_API_KEY'

  * Enable the following APIs & Services from [Your GCP Project > APIs & Services > API Library](https://console.cloud.google.com/apis/library?project=your-google-project-id)
  - [BigQuery API](https://console.cloud.google.com/apis/api/bigquery.googleapis.com/metrics?project=your-google-project-id)
  - [Generative Language API](https://console.cloud.google.com/apis/api/generativelanguage.googleapis.com/metrics?project=your-google-project-id)


You are going to use **your own Gemini API key**:
Login to your account (same account you use for the GCP project setups) in [Google AI Studio - API Keys](https://aistudio.google.com/app/api-keys) and generate a new Gemini API key, copy the value and save it:
    GEMINI_API_KEY='YOUR_GEMINI_API_KEY'


**NOTES** - Throughout the code execution:
* Make sure you are *authenticating* with **your account** to ***your GCP project**
* Using the same value assignment to the following environment variables:
  - 'your-google-project-id' AS `GOOGLE_CLOUD_PROJECT`
  - 'YOUR_GOOGLE_API_KEY' AS `GOOGLE_API_KEY`
  - 'YOUR_GEMINI_API_KEY' AS `GEMINI_API_KEY`


## Execution Guide - EXECUTION_GUID.md


## My GCP Project
[GooGle Cloud Console](https://console.cloud.google.com/welcome/new?project=ad-performance-analysis-agent)
```
    Name: "Ad Performance Analysis Agent"
    ID: "ad-performance-analysis-agent"
```

*NOTE:* If you want access to my GCP project, please contact me.

## Input Dataset

`bigquery-public-data.google_analytics_sample.ga_sessions_*`

* Public BigQuery dataset.

* The format and schema of the Google Analytics data that is imported into BigQuery - [Documentation](https://support.google.com/analytics/answer/3437719?hl=en)


[**Google Analytics Sample**](https://console.cloud.google.com/marketplace/product/obfuscated-ga360-data/obfuscated-ga360-data) - Twelve months (August 2016 to August 2017) of obfuscated Google Analytics 360 data from the [Google Merchandise Store](https://merch.google/)




## The Task

**References**

- [BigQuery meets ADK & MCP: Accelerate agent development with BigQuery's new first-party toolset](https://cloud.google.com/blog/products/ai-machine-learning/bigquery-meets-google-adk-and-mcp) 

- [ADK Agents for BigQuery Series — Part 1: Build a baseline agent for BigQuery with ADK](https://medium.com/google-cloud/)adk-agents-for-bigquery-series-40de8cf4e3ca


### Part 1 - Data Preparation and Exploration


**Documents**

- [GA Sessions - BigQuery Export schema](https://support.google.com/analytics/answer/3437719?hl=en)
- [Google Analytics Sample](https://console.cloud.google.com/marketplace/product/obfuscated-ga360-data/obfuscated-ga360-data?project=ad-performance-analysis-agent)

- References:

  - [Analyzing Google Analytics Big Query Data to determine Market Demographics and Product Seasonality with SQL](https://medium.com/@lucadoehling/analyzing-google-analytics-big-query-data-to-determine-market-demographics-and-product-seasonality-18278b319e0e)

  - [How to work with Google Analytics data in BigQuery](https://medium.com/swlh/how-to-handle-google-analytics-data-in-bigquery-f4307062eada)


**Dates range:**
  - Start - August 2016: 08-2016 
  - End - August 2017: 08-2017


**Data Preparation**

- Data normalization - set zeros, null like expressions and "(not set)" to `null`

**Monthly data querying:**

- BigQuery 
  - Table ID: `ad-performance-analysis-agent.ga_sessions_data.data`
  - Query: [`ad-performance-analysis-agent.Queries.BASE_QUERY`](https://console.cloud.google.com/bigquery?ws=!1m7!1m6!12m5!1m3!1sad-performance-analysis-agent!2sus-central1!3s42fb8b6f-761d-49d0-8ea7-c401a1be27b5!2e1)

- Code: `/Users/netagindes/Repos/teads-home-assignment/data/queries.py`

**Next Step [Optional]**

- Enrich the agent input channeling other fields from the GA Sample data.


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
