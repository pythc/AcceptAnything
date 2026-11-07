"""Build and start the local acceptance workbench; never listens publicly."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=18890)
parser.add_argument("--seed", action="store_true", help="Create real fixture runs when no executions exist")
args = parser.parse_args()
if not 1024 <= args.port <= 65535:
    parser.error("port must be between 1024 and 65535")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
from acceptance.engine import NODE, Store

if not NODE.is_file():
    parser.error("Node 24+ unavailable; set ACCEPTANCE_NODE to its absolute binary path")
major = int(subprocess.check_output([str(NODE), "--version"], text=True).lstrip("v").split(".")[0])
if major < 24:
    parser.error("Node 24+ is required")
os.environ["PATH"] = str(NODE.parent) + os.pathsep + os.environ.get("PATH", "")
subprocess.run([shutil.which("npm"), "run", "build"], cwd=ROOT / "web", check=True)
if args.seed:
    store = Store()
    if not store.list():
        for mode in ("buggy", "fixed"):
            with store.lease():
                run = store.create(mode)
                store.execute(run["id"])
                print(mode, store.snapshot(run["id"])["decision"])
os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "acceptance.api:app", "--host", "127.0.0.1", "--port", str(args.port)])
