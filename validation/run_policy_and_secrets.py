"""Run pinned OPA and Gitleaks containers offline on research inputs only."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("RESEARCH_EVIDENCE_DIR", str(ROOT / "research/evidence"))).resolve()
OPA = "openpolicyagent/opa@sha256:35615020f7224b7da7ccfe76dc3cb93bc43aab8a3b42099f32edc42cdbca27bf"
GITLEAKS = "ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f"
BASE = ["docker", "run", "--rm", "--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--read-only"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    samples = ROOT / "validation/secret-samples"
    for mode in ("buggy", "fixed"):
        (samples / mode).mkdir(parents=True, exist_ok=True)
    # Artificial pattern, never issued by a provider and never sent to a network.
    (samples / "buggy/config.txt").write_text('github_token = "ghp_7M9qL2vR8xN4bT6sP1cF5hJ3wK0yD9aE8uZ2"\n')
    (samples / "fixed/config.txt").write_text('github_token = os.environ["GITHUB_TOKEN"]\n')
    runs = []
    commands = [("opa-policy-tests", BASE + ["-v", str(ROOT/"validation/policy")+":/policy:ro", OPA, "test", "/policy", "--format=json"], 0)]
    for mode, expected in [("buggy", 1), ("fixed", 0)]:
        commands.append(("gitleaks-"+mode, BASE+["-v",str(samples/mode)+":/scan:ro","-v",str(OUT)+":/reports",GITLEAKS,"dir","/scan","--redact=100","--report-format","json","--report-path","/reports/gitleaks-"+mode+".json","--no-banner"], expected))
    for name, cmd, expected in commands:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        (OUT/(name+".log")).write_text(p.stdout+p.stderr)
        runs.append({"name":name,"exit_code":p.returncode,"expected_exit_code":expected,"matched":p.returncode==expected})
    summary = {"images":{"opa":OPA,"gitleaks":GITLEAKS},"runs":runs,"experiment_passed":all(r["matched"] for r in runs)}
    (OUT/"policy-secret-runs.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))
    if not summary["experiment_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
