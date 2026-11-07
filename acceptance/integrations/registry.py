"""Tool recipes are code-reviewed locally; HTTP callers cannot submit commands."""

import json
from pathlib import Path
from .formats import FORMATS

ROOT = Path(__file__).resolve().parents[2]


def tool(
    image,
    format,
    argv,
    report="report.json",
    exits=(0,),
    version=("--version",),
    network=False,
):
    return dict(
        image_key=image,
        format=format,
        argv=argv,
        report=report,
        exit_codes=list(exits),
        version_argv=list(version),
        registry_network=network,
    )


TOOLS = {
    **{'universal-'+name:tool('python','junit',[],report='report.xml',exits=(0,1),network=name in {'prepare','native','fixture'}) for name in ('design','prepare','build','native','service','business','cleanup','fixture')},
    **{'auto-go-'+name:tool('python' if name=='business' else 'auto-go','junit',[],report='report.xml',exits=(0,1),network=name=='dependencies') for name in ('dependencies','build','vet','native','business','cleanup')},
    "gmah-build": tool("gmah-web", "junit", [], report="report.xml", exits=(0, 1, 2)),
    "gmah-regression": tool("gmah-api", "junit", [], report="report.xml", exits=(0, 1)),
    "gmah-recovery": tool("gmah-api", "junit", [], report="report.xml", exits=(0, 1)),
    "gmah-performance": tool("gmah-k6", "k6", [], exits=(0, 99)),
    "acceptance-generated": tool("python", "junit", [], report="report.xml", exits=(0, 1), version=("pytest", "--version")),
    "bandit": tool(
        "python",
        "bandit",
        ["bandit", "-r", "{target}", "-f", "json", "-o", "/output/report.json"],
        exits=(0, 1),
        version=("bandit", "--version"),
    ),
    "ruff": tool(
        "python",
        "ruff",
        [
            "ruff",
            "check",
            "--no-cache",
            "--output-format",
            "json",
            "--output-file",
            "/output/report.json",
            "{target}",
        ],
        exits=(0, 1),
        version=("ruff", "--version"),
    ),
    "pytest": tool(
        "python",
        "junit",
        [
            "pytest",
            "-p",
            "no:cacheprovider",
            "--junitxml=/output/report.xml",
            "{target}",
        ],
        report="report.xml",
        exits=(0, 1),
        version=("pytest", "--version"),
    ),
    "pytest-allure": tool(
        "python",
        "allure",
        ["pytest", "-p", "no:cacheprovider", "--alluredir=/output/allure", "{target}"],
        report="allure",
        exits=(0, 1),
        version=("pytest", "--version"),
    ),
    "coverage": tool(
        "python",
        "cobertura",
        [
            "pytest",
            "-p",
            "no:cacheprovider",
            "--cov={target}",
            "--cov-report=xml:/output/report.xml",
            "{target}",
        ],
        report="report.xml",
        exits=(0, 1),
        version=("coverage", "--version"),
    ),
    "robot": tool(
        "python",
        "robot",
        [
            "robot",
            "--outputdir",
            "/output",
            "--output",
            "report.xml",
            "--log",
            "NONE",
            "--report",
            "NONE",
            "{target}",
        ],
        report="report.xml",
        exits=tuple(range(251)),
        version=("robot", "--version"),
    ),
    "pip-audit": tool(
        "python",
        "pip-audit",
        [
            "pip-audit",
            "--no-deps",
            "--disable-pip",
            "-r",
            "{target}",
            "-f",
            "json",
            "-o",
            "/output/report.json",
            "--progress-spinner",
            "off",
        ],
        exits=(0, 1),
        version=("pip-audit", "--version"),
        network=True,
    ),
    "checkov": tool(
        "python",
        "checkov",
        [
            "checkov",
            "--directory",
            "{target}",
            "--framework",
            "terraform",
            "dockerfile",
            "kubernetes",
            "--output",
            "json",
            "--quiet",
            "--skip-download",
        ],
        report="stdout",
        exits=(0, 1),
        version=("checkov", "--version"),
    ),
    "eslint": tool(
        "node",
        "eslint",
        [
            "eslint",
            "--no-config-lookup",
            "--no-ignore",
            "--rule",
            "no-undef:error",
            "--rule",
            "no-unused-vars:error",
            "--format",
            "json",
            "--output-file",
            "/output/report.json",
            "{target}",
        ],
        exits=(0, 1),
        version=("eslint", "--version"),
    ),
    "spectral": tool(
        "node",
        "spectral",
        [
            "spectral",
            "lint",
            "--ruleset",
            "/source/spectral.yaml",
            "--format",
            "json",
            "--output",
            "/output/report.json",
            "{target}",
        ],
        exits=(0, 1),
        version=("spectral", "--version"),
    ),
    "newman": tool(
        "node",
        "newman",
        [
            "newman",
            "run",
            "{target}",
            "--reporters",
            "json",
            "--reporter-json-export",
            "/output/report.json",
        ],
        exits=(0, 1),
        version=("newman", "--version"),
    ),
    "schemathesis": tool(
        "python",
        "junit",
        [
            "schemathesis",
            "run",
            "{target}",
            "--url",
            "http://127.0.0.1:19300",
            "--report",
            "junit",
            "--report-junit-path",
            "/output/report.xml",
            "--max-examples",
            "10",
            "--phases",
            "examples,coverage,fuzzing",
            "--generation-database",
            "none",
        ],
        report="report.xml",
        exits=(0, 1),
        version=("schemathesis", "--version"),
    ),
    "node-test": tool(
        "node-base",
        "junit",
        ["node", "--test", "--test-reporter=junit", "{target}"],
        report="stdout",
        exits=(0, 1),
        version=("node", "--version"),
    ),
    "npm-audit": tool(
        "node-base",
        "npm-audit",
        [
            "npm",
            "audit",
            "--json",
            "--ignore-scripts",
            "--prefix",
            "{target}",
            "--registry=https://registry.npmjs.org",
        ],
        report="stdout",
        exits=(0, 1),
        version=("npm", "--version"),
        network=True,
    ),
    "semgrep": tool(
        "semgrep",
        "semgrep",
        [
            "semgrep",
            "scan",
            "--oss-only",
            "--config",
            "/source/semgrep.yaml",
            "--metrics",
            "off",
            "--disable-version-check",
            "--no-git-ignore",
            "--error",
            "--json",
            "--output",
            "/output/report.json",
            "--jobs",
            "2",
            "--timeout",
            "15",
            "{target}",
        ],
        exits=(0, 1),
        version=("semgrep", "--version"),
    ),
    "semgrep-njsscan": tool(
        "semgrep",
        "semgrep",
        [
            "semgrep",
            "scan",
            "--oss-only",
            "--config",
            "/recipe/njsscan-rules.json",
            "--metrics",
            "off",
            "--disable-version-check",
            "--no-git-ignore",
            "--error",
            "--json",
            "--output",
            "/output/report.json",
            "--jobs",
            "2",
            "--timeout",
            "15",
            "{target}",
        ],
        exits=(0, 1),
        version=("semgrep", "--version"),
    ),
    "gitleaks": tool(
        "gitleaks",
        "gitleaks",
        [
            "dir",
            "{target}",
            "--redact=100",
            "--report-format",
            "json",
            "--report-path",
            "/output/report.json",
            "--no-banner",
        ],
        exits=(0, 1),
        version=("version",),
    ),
    "trivy-config": tool(
        "trivy",
        "trivy",
        [
            "config",
            "--skip-check-update",
            "--format",
            "json",
            "--output",
            "/output/report.json",
            "{target}",
        ],
        version=("--version",),
    ),
    "trivy-fs": tool(
        "trivy",
        "trivy",
        [
            "fs",
            "--scanners",
            "vuln",
            "--skip-version-check",
            "--db-repository",
            "ghcr.io/aquasecurity/trivy-db:2",
            "--db-repository",
            "public.ecr.aws/aquasecurity/trivy-db:2",
            "--format",
            "json",
            "--output",
            "/output/report.json",
            "{target}",
        ],
        version=("--version",),
        network=True,
    ),
    "syft-cyclonedx": tool(
        "syft",
        "cyclonedx",
        ["scan", "dir:{target}", "--output", "cyclonedx-json=/output/report.json"],
        version=("version",),
    ),
    "syft-spdx": tool(
        "syft",
        "spdx",
        ["scan", "dir:{target}", "--output", "spdx-json=/output/report.json"],
        version=("version",),
    ),
    "grype": tool(
        "grype",
        "grype",
        ["dir:{target}", "--output", "json", "--file", "/output/report.json"],
        version=("version",),
        network=True,
    ),
    "hadolint": tool(
        "hadolint",
        "hadolint",
        ["hadolint", "--format", "json", "{target}"],
        report="stdout",
        exits=(0, 1),
        version=("hadolint", "--version"),
    ),
    "shellcheck": tool(
        "shellcheck",
        "shellcheck",
        ["--format", "json1", "{target}"],
        report="stdout",
        exits=(0, 1),
    ),
}
IMAGES = {
    "python": "acceptance-python:d014",
    "node": "acceptance-node:d014",
    "node-base": "node:24-alpine",
    "semgrep": "semgrep/semgrep:latest",
    "gitleaks": "ghcr.io/gitleaks/gitleaks:latest",
    "trivy": "aquasec/trivy:latest",
    "syft": "anchore/syft:latest",
    "grype": "anchore/grype:latest",
    "hadolint": "hadolint/hadolint:latest",
    "shellcheck": "koalaman/shellcheck:stable",
}


def locks():
    path = ROOT / "integrations/toolchain.lock.json"
    return json.loads(path.read_text()) if path.exists() else {}


def catalog():
    pinned = locks()
    evidence_path = ROOT / "var/integrations/certification.json"
    evidence = json.loads(evidence_path.read_text()) if evidence_path.exists() else {}
    services = []
    for name in ("defectdojo", "reportportal", "sonarqube"):
        proof = ROOT / "var/integrations" / name / "live-verification.json"
        verified = json.loads(proof.read_text()) if proof.exists() else None
        item = {"id": name, "level": "contract-tested", "live_verified": False}
        if verified and verified.get("decision") == "reject" and verified.get("run_id"):
            item.update(
                level="real-service", live_verified=True, run_id=verified["run_id"]
            )
        if name == "defectdojo":
            types = ROOT / "var/integrations/defectdojo/test-types.json"
            native = ROOT / "var/integrations/defectdojo/native-verification.json"
            checked = (
                {x["scan_type"] for x in json.loads(native.read_text())}
                if native.exists()
                else set()
            )
            if verified and verified.get("reimport_deduplicated"):
                checked.add("Generic Findings Import")
            item["test_types"] = [
                {
                    "id": x["id"],
                    "name": x["name"],
                    "live_verified": x["name"] in checked,
                }
                for x in (
                    json.loads(types.read_text())["results"] if types.exists() else []
                )
            ]
        services.append(item)
    return {
        "formats": sorted(FORMATS),
        "executors": [
            {
                "id": k,
                **v,
                "image": pinned.get(v["image_key"]),
                "certification": evidence.get(k, {"level": "implemented-unverified"}),
            }
            for k, v in TOOLS.items()
        ],
        "services": services,
        "gate_kinds": [
            "metric",
            "delta",
            "new-findings",
            "licenses",
            "required-tests",
            "environments",
        ],
    }
