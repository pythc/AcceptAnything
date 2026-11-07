"""Publish catalog evidence only from complete, hash-verified real executions."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acceptance.integrations.store import IntegrationStore, now
from acceptance.integrations.runner import encode
from acceptance.integrations.registry import ROOT, TOOLS


def main():
    store = IntegrationStore()
    evidence = {}
    summary = []
    for rid in sys.argv[1:]:
        r = store.snapshot(rid)
        if (
            r["mode"] != "executor"
            or not r["integrity"]
            or r["status"] != "completed"
            or r["decision"] == "inconclusive"
        ):
            raise ValueError("Cannot certify incomplete execution: " + rid)
        summary.append(
            dict(
                id=rid,
                decision=r["decision"],
                tasks=len(r["tasks"]),
                artifacts=len(r["artifacts"]),
                integrity=True,
            )
        )
        for t in r["tasks"]:
            if t["state"] != "completed" or not t["report"]["complete"]:
                raise ValueError("Incomplete tool: " + t["id"])
            evidence[t["tool"]] = dict(
                level="real-execution",
                run_id=rid,
                task_id=t["id"],
                report_ref=t["report_ref"],
                verified_at=now(),
                adapter_digest=r["adapter_digest"],
                environment=r["context"]["environment"],
            )
    missing = set(TOOLS) - evidence.keys()
    if missing:
        raise ValueError("Uncertified recipes: " + ", ".join(sorted(missing)))
    (store.root / "certification.json").write_bytes(encode(evidence))
    result = dict(
        verified_at=now(), executions=summary, recipes=len(evidence), status="verified"
    )
    (ROOT / "docs/verification/d014/certification.json").write_bytes(encode(result))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
