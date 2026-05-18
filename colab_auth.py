"""
One-time Google OAuth2 setup for automatic Colab execution.

Run this once:
    python colab_auth.py

It opens a browser, you log in with your Google account, and it writes
GOOGLE_REFRESH_TOKEN / GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET to .env.

After this, the orchestrator can auto-upload and trigger Colab execution
without any browser interaction.

Prerequisites:
  1. Go to https://console.cloud.google.com
  2. Create a project → APIs & Services → Enable "Google Drive API"
  3. Create OAuth 2.0 credentials (Desktop app type)
  4. Download the credentials JSON and paste client_id + client_secret below
     (or set GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET env vars before running)
"""

import os
import json
from pathlib import Path

CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

if not CLIENT_ID or not CLIENT_SECRET:
    CLIENT_ID     = input("Paste your Google OAuth client_id: ").strip()
    CLIENT_SECRET = input("Paste your Google OAuth client_secret: ").strip()

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "google-auth-oauthlib", "-q"])
    from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
]

client_config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
    }
}

flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
creds = flow.run_local_server(port=0)

refresh_token = creds.refresh_token
print(f"\nRefresh token obtained.")

# Write to .env
env_path = Path(__file__).parent / ".env"
env_text = env_path.read_text() if env_path.exists() else ""

def _set_env(text: str, key: str, value: str) -> str:
    import re
    pattern = rf"^{key}=.*$"
    replacement = f"{key}={value}"
    if re.search(pattern, text, re.MULTILINE):
        return re.sub(pattern, replacement, text, flags=re.MULTILINE)
    return text + f"\n{replacement}\n"

env_text = _set_env(env_text, "GOOGLE_CLIENT_ID", CLIENT_ID)
env_text = _set_env(env_text, "GOOGLE_CLIENT_SECRET", CLIENT_SECRET)
env_text = _set_env(env_text, "GOOGLE_REFRESH_TOKEN", refresh_token)
env_path.write_text(env_text)

print(f".env updated with OAuth credentials.")
print("You can now run `sudo docker compose up -d` and Colab upload will be automatic.")
