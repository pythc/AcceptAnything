"""Use the real local ReportPortal API: launch, test items, finish, then import."""

from pathlib import Path
import json, os, sys, uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import httpx
from acceptance.integrations.services import Service
from acceptance.integrations.runner import encode
from acceptance.integrations.store import IntegrationStore, now

root = Path(__file__).resolve().parents[3]
work = root / "var/integrations/reportportal"
env = dict(x.split("=", 1) for x in (work / "local.env").read_text().splitlines())
with httpx.Client(
    base_url="http://127.0.0.1:18895", timeout=60, trust_env=False
) as client:
    r = client.post(
        "/uat/sso/oauth/token",
        auth=("ui", "uiman"),
        data={
            "grant_type": "password",
            "username": "superadmin",
            "password": env["RP_INITIAL_ADMIN_PASSWORD"],
        },
    )
    if r.status_code != 200:
        raise RuntimeError(
            "Local ReportPortal auth HTTP " + str(r.status_code) + " " + r.text[:200]
        )
    os.environ["ACCEPTANCE_LOCAL_RP_TOKEN"] = r.json()["access_token"]
service = Service("http://127.0.0.1:18895", "ACCEPTANCE_LOCAL_RP_TOKEN", "reportportal")
try:
    projects = service.request("api/v1/project/list")["content"]
    project = next(
        x["projectName"] for x in projects if x["projectName"] == "superadmin_personal"
    )
    prefix = "api/v1/" + project + "/"
    launch = service.request(
        prefix + "launch",
        method="POST",
        json={
            "name": "D014 live API bridge calibration",
            "startTime": now(),
            "mode": "DEFAULT",
            "attributes": [{"key": "scope", "value": "synthetic fixture"}],
        },
    )
    launch_uuid = launch["id"]
    for name, state in [("positive control", "PASSED"), ("negative control", "FAILED")]:
        item = service.request(
            prefix + "item",
            method="POST",
            json={
                "name": name,
                "startTime": now(),
                "launchUuid": launch_uuid,
                "type": "STEP",
            },
        )
        service.request(
            prefix + "item/" + item["id"],
            method="PUT",
            json={"endTime": now(), "launchUuid": launch_uuid, "status": state},
        )
    service.request(
        prefix + "launch/" + launch_uuid + "/finish",
        method="PUT",
        json={"endTime": now(), "status": "FAILED"},
    )
    listing = service.request(
        prefix + "launch", params={"filter.eq.uuid": launch_uuid, "page.size": 10}
    )
    rows = listing.get("content", [])
    rows = [x for x in rows if x.get("uuid") == launch_uuid]
    if len(rows) != 1:
        raise RuntimeError("Cannot locate exact launch ID")
    data = service.reportportal_pull(project, rows[0]["id"])
    store = IntegrationStore()
    with store.lease():
        run = store.import_reports(
            str(uuid.uuid4()),
            "ReportPortal · 真实服务测试结果同步",
            {
                "repository": "local synthetic fixture",
                "revision": "D014",
                "snapshot_digest": __import__("hashlib")
                .sha256(encode(data))
                .hexdigest(),
                "environment": "ReportPortal core / isolated Docker",
                "scope": "2 synthetic tests; launch + finish + paginated pull",
            },
            [{"id": "rp", "format": "reportportal", "raw": encode(data)}],
            [
                {
                    "id": "failures",
                    "kind": "metric",
                    "tasks": ["rp"],
                    "metric": "tests.failed",
                    "threshold": 0,
                }
            ],
        )
    result = {
        "service": "reportportal",
        "project": project,
        "launch_id": rows[0]["id"],
        "run_id": run["id"],
        "decision": run["decision"],
        "tests": len(run["tasks"][0].get("report", {}).get("tests", [])),
        "errors": run["errors"],
    }
    (work / "live-verification.json").write_bytes(encode(result))
    print(json.dumps(result, ensure_ascii=False))
finally:
    service.close()
    os.environ.pop("ACCEPTANCE_LOCAL_RP_TOKEN", None)
