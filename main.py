import os
import subprocess
import sys


if __name__ == "__main__":
    port = os.getenv("PORT", "8501")
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "frontend/app_streamlit.py",
        "--server.address",
        "0.0.0.0",
        "--server.port",
        port,
    ]
    raise SystemExit(subprocess.call(cmd))
