"""Register an explicit project contract or run it against a bounded snapshot."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acceptance.engine import Store
from acceptance import projects

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("action", choices=["register", "run", "list"])
parser.add_argument("target", nargs="?")
parser.add_argument("--data", type=Path)
args = parser.parse_args()
store = Store(args.data)
if args.action == "list":
    print(json.dumps(projects.profiles(store), ensure_ascii=False, indent=2))
elif not args.target:
    parser.error("register needs a JSON profile; run needs a registered ID")
elif args.action == "register":
    print(projects.register(store, json.loads(Path(args.target).read_bytes())))
else:
    with store.lease():
        run = projects.create(store, args.target)
        store.execute(run["id"])
    view = store.snapshot(run["id"])
    print(json.dumps({k: view[k] for k in ["id", "decision", "integrity", "validation", "reasons"]}, ensure_ascii=False, indent=2))
    sys.exit({"allow": 0, "reject": 1, "inconclusive": 2}[view["decision"]])
