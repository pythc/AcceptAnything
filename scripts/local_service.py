"""Manage the local preview with launchd, independently of a terminal/chat session.

The plist stays in this project's var directory; it is not installed at login.
"""

import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import time
import json
from urllib.request import build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parents[1]
LABEL = "cn.110lab.acceptance.local"
DOMAIN = f"gui/{os.getuid()}"
TARGET = DOMAIN + "/" + LABEL
STATE = ROOT / "var/local-service"
PLIST = STATE / (LABEL + ".plist")


def loaded():
    return subprocess.run(
        ["launchctl", "print", TARGET], capture_output=True
    ).returncode == 0


def ready():
    deadline = time.monotonic() + 120
    opener = build_opener(ProxyHandler({}))
    while time.monotonic() < deadline:
        try:
            with opener.open('http://127.0.0.1:18890/api/health', timeout=1) as response:
                if response.status == 200 and json.load(response).get('status') == 'ok':
                    return
        except (OSError, ValueError):
            pass
        time.sleep(0.2)
    raise RuntimeError('Local service was loaded but did not become ready; inspect var/local-service/stderr.log')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "stop", "status"))
    parser.add_argument("--worker", action="store_true", help="管理独立的 Huey 执行进程")
    args = parser.parse_args()
    global LABEL, TARGET, PLIST
    if args.worker:
        LABEL = "cn.110lab.acceptance.worker"
        TARGET = DOMAIN + "/" + LABEL
        PLIST = STATE / (LABEL + ".plist")
    if sys.platform != "darwin":
        parser.error("This launcher requires macOS launchd")
    if args.action == "status":
        return subprocess.run(["launchctl", "print", TARGET]).returncode
    if args.action == "stop":
        if loaded():
            subprocess.run(["launchctl", "bootout", TARGET], check=True)
            # bootout may return before launchd removes the service record.
            for _ in range(100):
                if not loaded():
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError("Service has not finished unloading; do not start a duplicate")
        return 0
    if args.action == "start" and not args.worker:
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "start", "--worker"], check=True)
    if loaded():
        if not args.worker: ready()
        print("Service already loaded: " + TARGET)
        return 0
    if not (ROOT / "web/dist/client/index.html").is_file():
        parser.error("Build the frontend before starting the service")
    STATE.mkdir(parents=True, exist_ok=True)
    config = {
        "Label": LABEL,
        "ProgramArguments": [
            str(ROOT / ".venv/bin/python"), "-m", "uvicorn",
            "acceptance.api:app", "--host", "127.0.0.1", "--port", "18890",
        ],
        "WorkingDirectory": str(ROOT),
        "EnvironmentVariables": {
            "PATH": "/Users/alex/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "PYTHONUNBUFFERED": "1",
            **({'ACCEPTANCE_PLANNER_CONFIG_FILE':str(ROOT/'var/planner-connection.json')} if (ROOT/'var/planner-connection.json').is_file() else {}),
            **{key: os.environ[key] for key in ('ACCEPTANCE_PLANNER_CONFIG_FILE','ACCEPTANCE_PLANNER_BASE_URL','ACCEPTANCE_PLANNER_MODEL','ACCEPTANCE_PLANNER_KEY_FILE','ACCEPTANCE_PLANNER_REASONING_EFFORT','ACCEPTANCE_PLANNER_PROVIDER','ACCEPTANCE_PLANNER_TIMEOUT_SECONDS','ACCEPTANCE_GIT_TRANSFER_TIMEOUT_SECONDS','ACCEPTANCE_COMPILER_JOBS') if key in os.environ},
        },
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 5,
        # HTTP serves the visible UI and cannot use XPC transactions to become
        # adaptive. Background classification throttles even page-in/database
        # reads under host load. Keep the execution worker in the background.
        "ProcessType": "Background" if args.worker else "Interactive",
        "StandardOutPath": str(STATE / "stdout.log"),
        "StandardErrorPath": str(STATE / "stderr.log"),
    }
    if args.worker:
        config["ProgramArguments"] = [str(ROOT / ".venv/bin/python"), "-m", "acceptance.jobs", "--root", str(ROOT / "var")]
        config["StandardOutPath"] = str(STATE / "worker-stdout.log")
        config["StandardErrorPath"] = str(STATE / "worker-stderr.log")
    PLIST.write_bytes(plistlib.dumps(config))
    PLIST.chmod(0o600)
    subprocess.run(["launchctl", "bootstrap", DOMAIN, str(PLIST)], check=True)
    if not args.worker: ready()
    print("Service loaded: " + TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
