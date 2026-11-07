from pathlib import Path
import json, os, sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import httpx
from acceptance.integrations.services import Service
from acceptance.integrations.runner import encode
from acceptance.integrations.store import IntegrationStore

root = Path(__file__).resolve().parents[3]
work = root / "var/integrations/defectdojo"
env = dict(line.split("=", 1) for line in (work / "local.env").read_text().splitlines())
with httpx.Client(
    base_url="http://127.0.0.1:18894", timeout=30, trust_env=False
) as client:
    response = client.post(
        "/api/v2/api-token-auth/",
        json={"username": "admin", "password": env["DD_ADMIN_PASSWORD"]},
    )
    response.raise_for_status()
    os.environ["ACCEPTANCE_LOCAL_DOJO_TOKEN"] = response.json()["token"]
service = Service("http://127.0.0.1:18894", "ACCEPTANCE_LOCAL_DOJO_TOKEN", "defectdojo")
store = IntegrationStore()
calibration = store.snapshot("int-94d7ae6631ac4999")
results = []
try:
    for tool, scan in [
        ("bandit", "Bandit Scan"),
        ("semgrep", "Semgrep JSON Report"),
        ("trivy-fs", "Trivy Scan"),
        ("grype", "Anchore Grype"),
    ]:
        task = next(t for t in calibration["tasks"] if t["id"] == tool)
        _, raw = store.artifact_bytes(calibration["id"], task["report_ref"])
        imported = service.dojo_import(raw, scan, engagement=1)
        test_id = imported["test"]
        test_id = test_id["id"] if isinstance(test_id, dict) else test_id
        data = service.dojo_pull(test_id)
        results.append(
            {
                "tool": tool,
                "scan_type": scan,
                "test_id": test_id,
                "findings": len(data["findings"]),
                "source_report_sha256": __import__("hashlib").sha256(raw).hexdigest(),
            }
        )
    (work / "native-verification.json").write_bytes(encode(results))
    print(json.dumps(results, ensure_ascii=False))
finally:
    service.close()
    os.environ.pop("ACCEPTANCE_LOCAL_DOJO_TOKEN", None)
