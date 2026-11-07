"""Provision an isolated local OSS service; never changes an existing Dojo instance."""

from pathlib import Path
import json, subprocess, secrets

root = Path(__file__).resolve().parents[3]
work = root / "var/integrations/defectdojo"
work.mkdir(parents=True, exist_ok=True)
envpath = work / "local.env"
if not envpath.exists():
    password = secrets.token_urlsafe(32)
    db = secrets.token_hex(24)
    envpath.write_text(
        "\n".join(
            [
                "DD_ADMIN_PASSWORD=" + password,
                "DD_DATABASE_URL=postgresql://defectdojo:"
                + db
                + "@postgres:5432/defectdojo",
                "POSTGRES_PASSWORD=" + db,
                "DD_SECRET_KEY=" + secrets.token_hex(32),
                "DD_CREDENTIAL_AES_256_KEY=" + secrets.token_hex(16),
            ]
        )
        + "\n"
    )
    envpath.chmod(0o600)


def image(tag):
    return json.loads(subprocess.check_output(["docker", "image", "inspect", tag]))[0][
        "Id"
    ]


django = image("defectdojo/defectdojo-django:latest")
common = {
    "image": django,
    "env_file": [str(envpath)],
    "environment": {
        "DD_ALLOWED_HOSTS": "localhost,127.0.0.1,uwsgi",
        "DD_DEBUG": "False",
        "DD_CELERY_BROKER_URL": "redis://valkey:6379/0",
        "DD_CACHE_URL": "redis://valkey:6379/1",
        "DD_DATABASE_READINESS_TIMEOUT": "60",
        "DD_CELERY_WORKER_CONCURRENCY": "1",
        "DD_UWSGI_NUM_OF_PROCESSES": "2",
    },
    "volumes": ["media:/app/media"],
    "mem_limit": "1536m",
    "cpus": 2,
}
services = {
    "postgres": {
        "image": image("postgres:17-alpine"),
        "environment": {
            "POSTGRES_DB": "defectdojo",
            "POSTGRES_USER": "defectdojo",
            "POSTGRES_PASSWORD": "${POSTGRES_PASSWORD}",
        },
        "volumes": ["postgres:/var/lib/postgresql/data"],
        "mem_limit": "512m",
    },
    "valkey": {"image": image("redis:8-alpine"), "mem_limit": "128m"},
    "initializer": {
        **common,
        "entrypoint": [
            "/wait-for-it.sh",
            "postgres:5432",
            "-t",
            "60",
            "--",
            "/entrypoint-initializer.sh",
        ],
        "environment": {
            **common["environment"],
            "DD_INITIALIZE": "true",
            "DD_ADMIN_USER": "admin",
            "DD_ADMIN_MAIL": "admin@localhost.invalid",
        },
        "depends_on": ["postgres"],
    },
    "uwsgi": {
        **common,
        "entrypoint": [
            "/wait-for-it.sh",
            "postgres:5432",
            "-t",
            "60",
            "--",
            "/entrypoint-uwsgi.sh",
        ],
        "depends_on": {
            "initializer": {"condition": "service_completed_successfully"},
            "valkey": {"condition": "service_started"},
        },
    },
    "celeryworker": {
        **common,
        "entrypoint": [
            "/wait-for-it.sh",
            "postgres:5432",
            "-t",
            "60",
            "--",
            "/entrypoint-celery-worker.sh",
        ],
        "depends_on": {
            "initializer": {"condition": "service_completed_successfully"},
            "valkey": {"condition": "service_started"},
        },
    },
    "nginx": {
        "image": image("defectdojo/defectdojo-nginx:latest"),
        "ports": ["127.0.0.1:18894:8080"],
        "environment": {"DD_UWSGI_HOST": "uwsgi", "DD_UWSGI_PORT": "3031"},
        "volumes": ["media:/usr/share/nginx/html/media"],
        "depends_on": ["uwsgi"],
        "mem_limit": "128m",
    },
}
(work / "compose.json").write_text(
    json.dumps(
        {
            "name": "acceptance-dojo-d014",
            "services": services,
            "volumes": {"media": {}, "postgres": {}},
            "networks": {
                "default": {"ipam": {"config": [{"subnet": "10.231.250.0/24"}]}}
            },
        },
        indent=2,
    )
    + "\n"
)
print(
    "Prepared isolated service at 127.0.0.1:18894; credentials retained only in a local 0600 file."
)
