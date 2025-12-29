import os
from pathlib import Path
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"

if ENV_PATH.exists():  # Load .env file from project root
    load_dotenv(dotenv_path=ENV_PATH)
else:
    # Environment variables should have been set using the terminal export commands
    pass


def fetch_required_env_var(name: str, default: str = None) -> str:
    value = os.getenv(name)

    if not value:
        if default:
            return default

        raise RuntimeError(
            f"Missing required environment variable: {name}\n"
        )
    return value


# Fetch required environment variables
GOOGLE_CLOUD_PROJECT: str = fetch_required_env_var("GOOGLE_CLOUD_PROJECT")
GEMINI_API_KEY: str = fetch_required_env_var("GEMINI_API_KEY")
GOOGLE_API_KEY: str = fetch_required_env_var("GOOGLE_API_KEY")
REGION: str = fetch_required_env_var("REGION", "US")


def main():

    if not all([GOOGLE_CLOUD_PROJECT, GEMINI_API_KEY, GOOGLE_API_KEY]):
        print("Missing required environment settings")

        if not ENV_PATH.exists():
            raise RuntimeError(
                f"""Missing required environment settings - 
                Go over the instructions in step [1] of the README.md file."""
            )
        
    return


if __name__ == "__main__":
    main()

    # print(f"GOOGLE_CLOUD_PROJECT: {GOOGLE_CLOUD_PROJECT}")
    # print(f"GEMINI_API_KEY: {GEMINI_API_KEY}")
    # print(f"GOOGLE_API_KEY: {GOOGLE_API_KEY}")
    # print(f"REGION: {REGION}")
