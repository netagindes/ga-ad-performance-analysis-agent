# Step by Step Guide for Ad Performance Analysis Agent

## [1] Code Alignment

Open a new terminal window.

If you already cloned to the `ga-ad-performance-analysis-agent` repository:
```bash
cd `PATH_TO/ga-ad-performance-analysis-agent`  # Set your terminal to the project root directory 
git status
git pull  # Pull all code updates
```

Else, clone to the `ga-ad-performance-analysis-agent` repository:
```bash
cd path_to_save  # Set your terminal to the place you want to save the code.
git clone git@github.com:netagindes/ga-ad-performance-analysis-agent.git  # Clone to the project's GitHub repository
cd ga-ad-performance-analysis-agent
```

## [2] GCP Authentication

Use *your account* to authenticate to *your GCP project* from the previous part, via gcloud CLI:

```bash
gcloud auth login  # Login to your account
gcloud auth application-default login
gcloud config set project your-google-project-id  # Set your GCP project as default
```

## [3] Validation - Make Sure:

* You are authenticated to *your account* and *your GCP project* is set as configuration default 

* You have:
  - **GOOGLE_CLOUD_PROJECT_ID** - *your GCP project* ID (`your-google-project-id`)
  - **GOOGLE_API_KEY** - extracted from *your GCP project* [APIs & Services > Credentials](https://console.cloud.google.com/apis/credentials?project=your-google-project-id)
  - **GEMINI_API_KEY** - generated for *your account* in [Google AI Studio - API Keys](https://aistudio.google.com/app/api-keys)


## [4] Code execution:

Use one of the following guides:
* 'Code Execution via Virtual Environment - Step by Step' from VENV_EXECUTION.md
* TODO! (docker)
* **[Optional] If you chose to use the Dockerfile** - Note that it references an earlier (less fine) version and needs to be fixed before running.
  - [Optional] run command:
```bash
docker compose up --build
docker compose up --force-recreate
```
  - Open Streamlit dashboard: [Ad Performances Analysis Agent](http://localhost:8502)
