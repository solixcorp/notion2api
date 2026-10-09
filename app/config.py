import os
import json
from dotenv import load_dotenv

# Load .env variables (override=True ensures .env takes precedence over system env)
load_dotenv(override=True)

REQUIRED_ACCOUNT_FIELDS = {"token_v2", "space_id", "user_id"}

def load_accounts():
    """
    Load account configuration from accounts.json or the NOTION_ACCOUNTS env var.
    Priority: accounts.json > NOTION_ACCOUNTS environment variable
    """
    # Try accounts.json first
    accounts_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "accounts.json")
    accounts_json = None

    if os.path.isfile(accounts_file):
        with open(accounts_file, "r", encoding="utf-8") as f:
            accounts_json = f.read().strip()
    
    # Fall back to environment variable
    if not accounts_json:
        accounts_json = os.getenv("NOTION_ACCOUNTS")

    if not accounts_json:
        raise ValueError("No account configuration found. Create an accounts.json file or set the NOTION_ACCOUNTS environment variable.")
    
    try:
        accounts = json.loads(accounts_json)
        if not isinstance(accounts, list) or len(accounts) == 0:
            raise ValueError("Invalid account configuration format. Expected a non-empty JSON array.")
        for idx, account in enumerate(accounts):
            if not isinstance(account, dict):
                raise ValueError(f"Account config[{idx}] must be an object.")
            missing = sorted(field for field in REQUIRED_ACCOUNT_FIELDS if not account.get(field))
            if missing:
                raise ValueError(f"Account config[{idx}] is missing required fields: {', '.join(missing)}")
        return accounts
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse account configuration: {e}")

# Global config objects
ACCOUNTS = load_accounts()

# FastAPI server configuration
API_KEY = os.getenv("API_KEY", "")
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",") if origin.strip()]

# APP_MODE: heavy (default), lite, or standard
APP_MODE = os.getenv("APP_MODE", "heavy").lower().strip()

def is_lite_mode() -> bool:
    return APP_MODE == "lite"

def is_standard_mode() -> bool:
    """Standard mode: sends full context, supports thinking and search output."""
    return APP_MODE == "standard"

def get_default_account():
    """Return the default account (first entry in the list)."""
    return ACCOUNTS[0]
