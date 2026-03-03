"""Startup script that decodes GOOGLE_CREDENTIALS_B64 env var to a file, then runs main.py."""

import os
import base64
import subprocess
import sys

# If GOOGLE_CREDENTIALS_B64 is set, decode it to credentials.json
creds_b64 = os.getenv("GOOGLE_CREDENTIALS_B64", "")
if creds_b64:
    creds_path = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    with open(creds_path, "wb") as f:
        f.write(base64.b64decode(creds_b64))
    print(f"Decoded Google credentials to {creds_path}")

# Run main.py
sys.exit(subprocess.call([sys.executable, "main.py"]))
