# Code Execution via Virtual Environment - Step by Step

## **Make sure:**

* You are authenticated to *your account* and *your GCP project* is set as configuration default 

* You have the values for:
  - **GOOGLE_CLOUD_PROJECT_ID** - *your GCP project* ID (`your-google-project-id`)
  - **GOOGLE_API_KEY** - extracted from *your GCP project* [APIs & Services > Credentials](https://console.cloud.google.com/apis/credentials?project=your-google-project-id)
  - **GEMINI_API_KEY** - generated for *your account* in [Google AI Studio - API Keys](https://aistudio.google.com/app/api-keys)


## [0] Open a terminal window set to the project's root:
```bash
cd `PATH_TO/ga-ad-performance-analysis-agent`  # Set your terminal to the project root directory
```
## [1] Environment Setups

### [1.1] Virtual Environment Setup
```bash
python -m venv .venv  # Create a Virtual 
source .venv/bin/activate  # Activate your virtual environment (.venv)
pip install -r requirements.txt  # Install the project's requirements
```

## [1.2] Environment Variables Setup

Chose one of the following options:

* **Option A - Command Line**

```bash
  export GOOGLE_CLOUD_PROJECT='add-your-google-project'
  export GEMINI_API_KEY='ADD_YOUR_GEMINI_API_KEY'
  export GOOGLE_API_KEY='ADD_YOUR_GOOGLE_API_KEY'
  export REGION='US'
```

* **Option B - .env File**
Create an .env file:
```bash
touch .env
```

Open the new .env file and add:
```
GEMINI_API_KEY="your-gemini-token"

GOOGLE_CLOUD_PROJECT="your-google-project-id"
GOOGLE_API_KEY="your-google-token"
```

## [1.3] Run Configuration Check [Optional]
```bash
python ./src/config.py
```

[2] [Optional] Run the MCP server 
```bash
pip install "mcp[cli]"
mcp dev src/ga_ad_agent/ga_mcp_server.py
```
**NOTE:** If you ran the MCP server, you should keep the server running and continue using a different terminal window (set to the project root with active environment)


[3] Run Ad Performance Analysis Agent Dashboard
```bash
streamlit run src/ga_ad_agent/agent_app.py
```
