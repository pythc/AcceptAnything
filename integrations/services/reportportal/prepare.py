"""Local ReportPortal core API validation, derived from pinned upstream Compose.

The optional ML analyzer and browser UI are not part of this API bridge test.
"""

from pathlib import Path
import json, subprocess, secrets
import yaml

root = Path(__file__).resolve().parents[3]
folder = Path(__file__).parent
work = root / "var/integrations/reportportal"
work.mkdir(parents=True, exist_ok=True)
(folder / "upstream.json").write_text(
    json.dumps(
        {
            "repository": "https://github.com/reportportal/reportportal",
            "commit": "e0bb071de9c07dfc4c3ddaf55de621853feccf2b",
        },
        indent=2,
    )
)
p = work / "local.env"
if not p.exists():
    p.write_text(
        "\n".join(
            k + "=" + secrets.token_hex(24)
            for k in (
                "POSTGRES_PASSWORD",
                "RABBITMQ_DEFAULT_PASS",
                "RP_INITIAL_ADMIN_PASSWORD",
            )
        )
        + "\n"
    )
    p.chmod(0o600)
d = yaml.safe_load((folder / "docker-compose.yml").read_text())
keys = ["postgres", "rabbitmq", "migrations", "api", "uat", "jobs"]
services = {k: d["services"][k] for k in keys}


def image(tag):
    return json.loads(subprocess.check_output(["docker", "image", "inspect", tag]))[0][
        "Id"
    ]


for name, s in services.items():
    for k in ["build", "profiles", "labels", "restart", "logging", "container_name"]:
        s.pop(k, None)
    if isinstance(s.get("depends_on"), dict):
        s["depends_on"] = {k: v for k, v in s["depends_on"].items() if k in keys}
    s["image"] = (
        s["image"].strip("${}").split("-", 1)[1]
        if s["image"].startswith("${")
        else s["image"]
    )
    s["image"] = image("postgres:17-alpine" if name == "postgres" else s["image"])
    s["mem_limit"] = (
        "1200m" if name in {"api", "jobs"} else "768m" if name == "uat" else "512m"
    )
    s["cpus"] = 2
    if name in {"api", "jobs", "uat"}:
        s["environment"]["JAVA_OPTS"] = (
            "-Xms128m -Xmx640m -Djava.security.egd=file:/dev/./urandom --add-opens=java.base/java.lang=ALL-UNNAMED"
        )
    if name == "postgres":
        s["volumes"] = ["postgres:/var/lib/postgresql/data"]
nginx = work / "nginx.conf"
nginx.write_text(
    'events {}\nhttp { server { listen 8080; location /api/ { proxy_pass http://api:8585/; } location /uat/ { proxy_pass http://uat:9999/; } location /health { return 200 "ready"; } } }\n'
)
services["gateway"] = {
    "image": image("nginx:alpine"),
    "volumes": [str(nginx) + ":/etc/nginx/nginx.conf:ro"],
    "ports": ["127.0.0.1:18895:8080"],
    "networks": ["reportportal"],
    "depends_on": ["api", "uat"],
    "mem_limit": "128m",
}
compose = {
    "name": "acceptance-rp-d014",
    "services": services,
    "configs": d["configs"],
    "volumes": {"storage": {}, "postgres": {}},
    "networks": {"reportportal": {"ipam": {"config": [{"subnet": "10.231.251.0/24"}]}}},
}
(work / "compose.json").write_text(json.dumps(compose, indent=2) + "\n")
print("Prepared local ReportPortal core API at 127.0.0.1:18895")
