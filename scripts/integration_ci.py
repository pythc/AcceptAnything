"""CI entrypoint: execute a registered profile, always export evidence, retain gate exit code."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.runner import encode
from acceptance.integrations import export


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    store = IntegrationStore()
    with store.lease():
        run = store.create(args.profile)
        run = store.execute(run["id"])
    (args.output / "run.json").write_bytes(encode(run))
    for kind, suffix in [("junit", "xml"), ("sarif", "sarif"), ("markdown", "md")]:
        (args.output / ("report." + suffix)).write_bytes(getattr(export, kind)(run))
    print(run["id"], run["decision"])
    return {"allow": 0, "reject": 1, "inconclusive": 2}[run["decision"]]


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
