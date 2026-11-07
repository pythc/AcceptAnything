"""Repeatable no-model component experiment; only targets the loopback fixture."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "validation"
OUT = Path(os.environ.get("RESEARCH_EVIDENCE_DIR", str(ROOT / "research/evidence"))).resolve()
NODE = Path(os.environ.get("RESEARCH_NODE", "/Users/alex/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"))
ENV = {**os.environ, "PATH": str(NODE.parent) + os.pathsep + os.environ["PATH"], "RESEARCH_EVIDENCE_DIR": str(OUT)}


def run(name, argv, cwd=HERE, env=None, timeout=60):
    start = time.monotonic()
    with (OUT / (name + ".log")).open("w") as log:
        proc = subprocess.run([str(a) for a in argv], cwd=cwd, env=env or ENV, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
    return {"name": name, "command": [str(a) for a in argv], "exit_code": proc.returncode, "seconds": round(time.monotonic()-start, 3)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    suite = HERE / "tests/acceptance.spec.mjs"
    baseline = hashlib.sha256(suite.read_bytes()).hexdigest()
    for mode in ("buggy", "fixed"):
        results.append(run("playwright-"+mode, [NODE, HERE/"node_modules/playwright/cli.js", "test"], env={**ENV,"FIXTURE_MODE": mode}))
        proc = subprocess.Popen([str(HERE/".venv/bin/python"), str(HERE/"fixture.py"), "--mode", mode, "--port", "18872"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(50):
                if proc.poll() is not None:
                    raise RuntimeError("fixture exited before readiness; possible port conflict")
                try:
                    with urlopen("http://127.0.0.1:18872/health", timeout=0.5) as r:
                        if json.load(r)["mode"] == mode:
                            break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("fixture not ready")
            results.append(run("schemathesis-"+mode, [HERE/".venv/bin/schemathesis", "run", "openapi.json", "--url", "http://127.0.0.1:18872", "--phases", "fuzzing", "--checks", "response_schema_conformance", "--mode", "positive", "--max-examples", "10", "--seed", "20261017", "--report", "junit,har,json", "--report-dir", OUT/("schemathesis-"+mode)]))
        finally:
            proc.terminate()
            proc.wait(timeout=5)
        results.append(run("bandit-"+mode, [HERE/".venv/bin/bandit", "-q", "-t", "B602", "static-samples/"+mode+".py", "-f", "json", "-o", OUT/("bandit-"+mode+".json")]))
    results.append(run("gauntlet-validator-probe", [HERE/"node_modules/@oven/bun-darwin-aarch64/bin/bun", "gauntlet-probe.ts"]))
    after = hashlib.sha256(suite.read_bytes()).hexdigest()
    checks = {"suite_unchanged":baseline==after}
    expected_codes = {"playwright-buggy":1,"playwright-fixed":0,"schemathesis-buggy":1,"schemathesis-fixed":0,"bandit-buggy":1,"bandit-fixed":0,"gauntlet-validator-probe":0}
    for result in results:
        checks[result["name"]+"_exit"] = result["exit_code"] == expected_codes[result["name"]]
    for mode, passed, failed in [("buggy",1,6),("fixed",7,0)]:
        stats=json.loads((OUT/("playwright-"+mode)/"results.json").read_text())["stats"]
        checks["playwright_"+mode+"_counts"] = stats["expected"]==passed and stats["unexpected"]==failed and stats["skipped"]==0 and stats["flaky"]==0
    probes=json.loads((OUT/"gauntlet-validator-probe.log").read_text())
    checks["gauntlet_probe"] = all(probes[k]["ok"]==v for k,v in {"missing_evidence":False,"unverified_artifact_reference":True,"rewritten_criterion":True,"contradictory_overall_pass":False}.items())
    manifest = {"suite_sha256_before":baseline,"suite_sha256_after":after,"suite_unchanged":baseline==after,"runs":results,"experiment_checks":checks,"experiment_passed":all(checks.values())}
    (OUT/"component-runs.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(manifest,indent=2))
    if not manifest["experiment_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
