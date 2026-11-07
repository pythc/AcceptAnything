"""Read-only consistency review of this research bundle, not a production verifier."""
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/evidence"


def main():
    checks = {}
    for prefix in ("", "repro-check/"):
        for mode, passed, failed in [("buggy",1,6),("fixed",7,0)]:
            stats = json.loads((OUT/(prefix+"playwright-"+mode)/"results.json").read_text())["stats"]
            checks[prefix+"playwright-"+mode] = stats["expected"]==passed and stats["unexpected"]==failed and stats["skipped"]==0 and stats["flaky"]==0
        runs=json.loads((OUT/(prefix+"component-runs.json")).read_text())
        current=hashlib.sha256((ROOT/"validation/tests/acceptance.spec.mjs").read_bytes()).hexdigest()
        checks[prefix+"suite-frozen"] = current==runs["suite_sha256_before"]==runs["suite_sha256_after"]
        if prefix:
            checks["reproduction-driver"] = runs["experiment_passed"] is True
    for name, count in [("strix",56),("test-agent",56)]:
        suites=list(ET.parse(OUT/(name+"-unit-tests.xml")).getroot().iter("testsuite"))
        checks[name+"-upstream-tests"]=sum(int(s.attrib["tests"]) for s in suites)==count and all(int(s.attrib.get(k,0))==0 for s in suites for k in ["failures","errors","skipped"])
    gauntlet=(OUT/"gauntlet-unit-tests.log").read_text()
    checks["gauntlet-upstream-tests"]="96 pass" in gauntlet and "0 fail" in gauntlet
    for prefix in ("", "repro-check/"):
        tests=json.loads((OUT/(prefix+"opa-policy-tests.log")).read_text())
        checks[prefix+"opa-policy"]=len(tests)==21 and all(not t.get("fail") and not t.get("error") for t in tests)
        for mode,count in [("buggy",1),("fixed",0)]:
            findings=json.loads((OUT/(prefix+"gitleaks-"+mode+".json")).read_text())
            checks[prefix+"gitleaks-"+mode]=len(findings)==count
            checks[prefix+"gitleaks-redacted-"+mode]=all(f.get("Secret")=="REDACTED" for f in findings)
    rows=json.loads((OUT/"source-file-manifest.json").read_text())
    checks["source-snapshots"]=all((ROOT/r["local_path"]).is_file() and hashlib.sha256((ROOT/r["local_path"]).read_bytes()).hexdigest()==r["sha256"] and r["commit_pinned"] for r in rows)
    missing=[]
    for path in [ROOT/"README.md", ROOT/"validation/README.md", *list((ROOT/"docs").glob("*.md"))]:
        for link in re.findall(r'\]\((/[^)]+)\)',path.read_text()):
            target=re.sub(r':\d+$','',link)
            if not Path(target).exists():missing.append({"document":str(path),"target":target})
    checks["local-document-links"] = not missing
    index=json.loads((OUT/"artifact-index.json").read_text())
    checks["artifact-digests"]=all((ROOT/r["path"]).is_file() and (ROOT/r["path"]).stat().st_size==r["bytes"] and hashlib.sha256((ROOT/r["path"]).read_bytes()).hexdigest()==r["sha256"] for r in index["artifacts"])
    print(json.dumps({"checks":checks,"missing_links":missing,"passed":all(checks.values())},indent=2))
    if not all(checks.values()):raise SystemExit(1)


if __name__ == "__main__":
    main()
