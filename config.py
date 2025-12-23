import os
from pathlib import Path
from dotenv import load_dotenv


ENV_PATH = Path(__file__).resolve().parent / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    # .env is optional; this is normal in CI / production
    pass


def fetch_required_env_var(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}\n"
            f"Did you forget to set it or create a .env file?"
        )
    return value


# OPENAI_API_KEY: str = fetch_required_env_var("OPENAI_API_KEY")
GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "ad-performance-analysis-agent")


def main():
    # print(f"OPENAI_API_KEY: {OPENAI_API_KEY}")
    # print(f"GOOGLE_CLOUD_PROJECT: {GOOGLE_CLOUD_PROJECT}")
    return


if __name__ == "__main__":
    main()
