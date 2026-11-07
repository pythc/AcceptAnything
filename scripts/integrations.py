"""Integration workbench CLI: provision, register, execute, import and export."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acceptance.integrations import export
from acceptance.integrations.registry import ROOT, TOOLS, IMAGES, catalog
from acceptance.integrations.runner import encode
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.services import Service


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path)
    sub = p.add_subparsers(dest="action", required=True)
    sub.add_parser("catalog")
    sub.add_parser("provision")
    sub.add_parser("list")
    sub.add_parser("profiles")
    for name in ("register", "run", "cancel", "verify"):
        c = sub.add_parser(name)
        c.add_argument("target")
    c = sub.add_parser("import")
    c.add_argument("manifest", type=Path)
    c = sub.add_parser("sync")
    c.add_argument("config", type=Path)
    c = sub.add_parser("track")
    c.add_argument("config", type=Path)
    c.add_argument("target")
    c.add_argument("task")
    c = sub.add_parser("service-import")
    c.add_argument("config", type=Path)
    c.add_argument("report", type=Path)
    c = sub.add_parser("export")
    c.add_argument("target")
    c.add_argument(
        "--format", choices=["junit", "sarif", "markdown", "json"], required=True
    )
    c.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    store = IntegrationStore(a.data)
    if a.action == "catalog":
        result = catalog()
    elif a.action == "provision":
        result = {}
        for key, tag in IMAGES.items():
            image = json.loads(
                subprocess.check_output(["docker", "image", "inspect", tag])
            )[0]
            versions = {}
            for name, spec in TOOLS.items():
                if spec["image_key"] != key:
                    continue
                try:
                    container = "acceptance-version-" + uuid.uuid4().hex[:12]
                    r = subprocess.run(
                        [
                            "docker",
                            "run",
                            "--name",
                            container,
                            "--rm",
                            "--network",
                            "none",
                            "--cap-drop",
                            "ALL",
                            "--memory",
                            "512m",
                            image["Id"],
                            *spec["version_argv"],
                        ],
                        capture_output=True,
                        timeout=90,
                    )
                    versions[name] = {
                        "exit_code": r.returncode,
                        "text": (r.stdout + r.stderr).decode(errors="replace")[:3000],
                    }
                except subprocess.TimeoutExpired:
                    versions[name] = {"error": "version-timeout"}
                finally:
                    subprocess.run(
                        ["docker", "rm", "-f", container],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=15,
                    )
            result[key] = {
                "id": image["Id"],
                "repo_digests": image.get("RepoDigests", []),
                "requested_tag": tag,
                "versions": versions,
            }
        (ROOT / "integrations/toolchain.lock.json").write_bytes(encode(result))
    elif a.action == "profiles":
        result = store.profiles()
    elif a.action == "list":
        result = store.list()
    elif a.action == "register":
        result = {"id": store.register(json.loads(Path(a.target).read_bytes()))}
    elif a.action == "cancel":
        result = store.cancel(a.target)
    elif a.action == "verify":
        result = store.snapshot(a.target)
    elif a.action == "run":
        with store.lease():
            r = store.create(a.target)
            print(
                json.dumps({"id": r["id"], "status": "queued"}),
                flush=True,
                file=sys.stderr,
            )
            result = store.execute(r["id"])
    elif a.action == "import":
        data = json.loads(a.manifest.read_bytes())
        reports = [
            {
                "id": x["id"],
                "format": x["format"],
                "raw": (a.manifest.parent / x["path"]).read_bytes(),
                **({"environment": x["environment"]} if "environment" in x else {}),
            }
            for x in data["reports"]
        ]
        with store.lease():
            result = store.import_reports(
                data["request_id"],
                data["name"],
                data["context"],
                reports,
                data["rules"],
            )
    elif a.action == "track":
        from acceptance.integrations.lifecycle import DojoLifecycle
        c = json.loads(a.config.read_bytes())
        service = Service(c["url"], c["token_env"], "defectdojo")
        try:
            result = DojoLifecycle(store.root / "lifecycle").publish(store,service,a.target,a.task,c["engagement"])
        finally: service.close()
    elif a.action == "service-import":
        c = json.loads(a.config.read_bytes())
        service = Service(c["url"], c["token_env"], "defectdojo")
        try:
            result = service.dojo_import(
                a.report.read_bytes(),
                c["scan_type"],
                c.get("engagement"),
                c.get("test_id"),
                a.report.name,
            )
        finally:
            service.close()
    elif a.action == "sync":
        c = json.loads(a.config.read_bytes())
        service = Service(c["url"], c["token_env"], c["service"])
        try:
            if c["service"] == "defectdojo":
                d = service.dojo_pull(c["test_id"])
                kind = "defectdojo-api"
            elif c["service"] == "reportportal":
                d = service.reportportal_pull(c["project"], c["launch_id"])
                kind = "reportportal"
            elif c["service"] == "sonarqube":
                d = service.sonar_pull(
                    c["project"], c["branch"], c["context"]["revision"]
                )
                kind = "sonarqube"
            else:
                raise ValueError("未注册服务")
        finally:
            service.close()
        with store.lease():
            result = store.import_reports(
                c["request_id"],
                c["name"],
                c["context"],
                [{"id": "remote", "format": kind, "raw": encode(d)}],
                c["rules"],
            )
    else:
        r = store.snapshot(a.target)
        raw = encode(r) if a.format == "json" else getattr(export, a.format)(r)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_bytes(raw)
        result = {"output": str(a.output.resolve())}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if a.action in {"run", "import", "sync", "verify"}:
        return {"allow": 0, "reject": 1, "inconclusive": 2}[result["decision"]]
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
