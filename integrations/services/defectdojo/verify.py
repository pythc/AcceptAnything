"""Live verification against the isolated instance created by prepare.py."""

from pathlib import Path
import json, os, sys, uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import httpx
from acceptance.integrations.services import Service
from acceptance.integrations.runner import encode
from acceptance.integrations.store import IntegrationStore

root = Path(__file__).resolve().parents[3]
work = root / "var/integrations/defectdojo"
env = dict(line.split("=", 1) for line in (work / "local.env").read_text().splitlines())
client = httpx.Client(base_url="http://127.0.0.1:18894", timeout=60, trust_env=False)
response = client.post(
    "/api/v2/api-token-auth/",
    json={"username": "admin", "password": env["DD_ADMIN_PASSWORD"]},
)
if response.status_code != 200:
    raise RuntimeError("Local Dojo authentication status " + str(response.status_code))
os.environ["ACCEPTANCE_LOCAL_DOJO_TOKEN"] = response.json()["token"]
service = Service("http://127.0.0.1:18894", "ACCEPTANCE_LOCAL_DOJO_TOKEN", "defectdojo")
try:
    version = {
        "image_digest": __import__("subprocess")
        .check_output(
            [
                "docker",
                "image",
                "inspect",
                "defectdojo/defectdojo-django:latest",
                "--format",
                "{{.Id}}",
            ],
            text=True,
        )
        .strip()
    }
    types = service.request("api/v2/test_types/?limit=1000")
    (work / "test-types.json").write_bytes(encode(types))
    product_types = service.request("api/v2/product_types/?limit=1")
    if product_types["results"]:
        product_type = product_types["results"][0]["id"]
    else:
        product_type = service.request(
            "api/v2/product_types/", method="POST", json={"name": "Acceptance D014"}
        )["id"]
    product = service.request(
        "api/v2/products/",
        method="POST",
        json={
            "name": "Acceptance D014 calibration " + uuid.uuid4().hex[:8],
            "description": "Synthetic integration verification. No production data.",
            "prod_type": product_type,
        },
    )
    engagement = service.request(
        "api/v2/engagements/",
        method="POST",
        json={
            "name": "D014 import verification",
            "product": product["id"],
            "target_start": "2026-10-17",
            "target_end": "2026-10-17",
            "status": "In Progress",
            "engagement_type": "CI/CD",
        },
    )
    scan = {
        "findings": [
            {
                "title": "Synthetic finding for adapter validation",
                "description": "Fixture only: this finding validates import, retrieval, evidence and gate behavior.",
                "severity": "High",
                "cwe": 79,
                "unique_id_from_tool": "acceptance-d014-fixture",
                "file_path": "fixture.py",
                "line": 1,
            }
        ]
    }
    imported = service.dojo_import(
        encode(scan), "Generic Findings Import", engagement=engagement["id"]
    )
    test_id = imported["test"]
    if isinstance(test_id, dict):
        test_id = test_id["id"]
    data = service.dojo_pull(test_id)
    if len(data["findings"]) != 1:
        raise RuntimeError("Dojo imported finding missing")
    # Reimport the same identity without auto-closing findings; verify no duplicate.
    repeated = service.dojo_import(
        encode(scan), "Generic Findings Import", test_id=test_id
    )
    data = service.dojo_pull(test_id)
    if len(data["findings"]) != 1:
        raise RuntimeError("Dojo reimport created duplicate")
    result = {
        "service": "defectdojo",
        "version": version,
        "test_types_count": types["count"],
        "product_id": product["id"],
        "engagement_id": engagement["id"],
        "test_id": test_id,
        "findings": len(data["findings"]),
        "reimport_deduplicated": True,
    }
    (work / "live-verification.json").write_bytes(encode(result))
    store = IntegrationStore()
    with store.lease():
        run = store.import_reports(
            str(uuid.uuid4()),
            "DefectDojo · 真实服务导入/重导入验证",
            {
                "repository": "local synthetic fixture",
                "revision": "D014",
                "snapshot_digest": __import__("hashlib")
                .sha256(encode(scan))
                .hexdigest(),
                "environment": "DefectDojo OSS / isolated Docker",
                "scope": "one synthetic finding; import + reimport + paginated retrieval",
            },
            [{"id": "dojo", "format": "defectdojo-api", "raw": encode(data)}],
            [
                {
                    "id": "high",
                    "kind": "metric",
                    "tasks": ["dojo"],
                    "metric": "findings.high",
                    "threshold": 0,
                }
            ],
        )
    result["run_id"] = run["id"]
    result["decision"] = run["decision"]
    (work / "live-verification.json").write_bytes(encode(result))
    print(json.dumps(result, ensure_ascii=False))
finally:
    service.close()
    client.close()
    os.environ.pop("ACCEPTANCE_LOCAL_DOJO_TOKEN", None)
