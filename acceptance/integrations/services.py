"""Official API bridges. Credentials are environment references, never persisted.

These clients connect to a user-configured instance; contract tests do not certify
an unconfigured commercial account. GET is retryable; mutations are never retried.
"""

import os
import json
import re
import time
from urllib.parse import urlparse, urljoin
import httpx
from .formats import require, json_data, base, finding, test, number


class Service:
    def __init__(self, url, token_env, kind, transport=None):
        parsed = urlparse(url)
        require(
            parsed.scheme == "https"
            or (
                parsed.scheme == "http"
                and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
            ),
            "外部服务必须使用 HTTPS",
        )
        require(
            not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment,
            "服务 URL 不能含凭据/查询串",
        )
        require(
            re.fullmatch(r"[A-Z][A-Z0-9_]{0,100}", token_env), "需要环境变量凭据引用"
        )
        token = os.environ.get(token_env)
        require(token, "缺少凭据环境变量 " + token_env)
        self.url = url.rstrip("/") + "/"
        self.kind = kind
        self.raw = []
        self.client = httpx.Client(
            timeout=30,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
            headers={
                "Authorization": ("Token " if kind == "defectdojo" else "Bearer ")
                + token,
                "Accept": "application/json",
            },
        )

    def close(self):
        self.client.close()

    def request(self, path, method="GET", **kwargs):
        url = urljoin(self.url, path)
        require(
            urlparse(url).netloc == urlparse(self.url).netloc
            and url.startswith(self.url),
            "拒绝跨源 API 或分页链接",
        )
        for attempt in range(3 if method == "GET" else 1):
            with self.client.stream(method, url, **kwargs) as response:
                if (
                    method == "GET"
                    and response.status_code in {429, 502, 503, 504}
                    and attempt < 2
                ):
                    delay = response.headers.get("Retry-After", "1")
                    time.sleep(min(float(delay) if delay.isdigit() else 1, 2))
                    continue
                require(
                    200 <= response.status_code < 300,
                    f"服务 {self.kind} 返回 HTTP {response.status_code}；未自动重试写入",
                )
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                result = json_data(data)
                self.raw.append({"path": path, "method": method, "response": result})
                return result
        raise ValueError("API 未返回成功结果")

    def dojo_pull(self, test_id):
        require(isinstance(test_id, int) and test_id > 0, "需要 Test ID")
        identity = self.request(f"api/v2/tests/{test_id}/")
        path = f"api/v2/findings/?test={test_id}&limit=100"
        rows = []
        visited = set()
        expected = None
        while True:
            require(path not in visited, "DefectDojo 分页循环")
            visited.add(path)
            d = self.request(path)
            require(
                isinstance(d.get("results"), list) and isinstance(d.get("count"), int),
                "DefectDojo 分页格式错误",
            )
            if expected is None:
                expected = d["count"]
            require(expected == d["count"], "拉取期间结果总数变化；需要重新读取")
            for row in d["results"]:
                require(row.get("test") == test_id, "结果属于其他 Test")
            rows.extend(d["results"])
            if not d.get("next"):
                break
            path = d["next"]
        require(
            len(rows) == expected and len({r["id"] for r in rows}) == len(rows),
            "DefectDojo 分页缺失/重复",
        )
        return {"test": identity, "findings": rows, "responses": self.raw}

    def dojo_import(
        self, raw, scan_type, engagement=None, test_id=None, filename="report.json", *, close_old=False, commit=None, build=None
    ):
        require(bool(engagement) ^ bool(test_id), "指定 engagement 或 test 之一")
        require(
            isinstance(scan_type, str) and scan_type and len(raw)>0,
            "扫描类型/报告无效",
        )
        require(re.fullmatch(r"[a-zA-Z0-9_.-]{1,200}", filename), "上传文件名无效")
        # Keep upstream findings alive unless an operator reviews same-scope completeness.
        data = {
            "scan_type": scan_type,
            "active": "true",
            "verified": "false",
            "close_old_findings": "true" if close_old else "false",
            "close_old_findings_product_scope": "false",
            "auto_create_context": "false",
            "minimum_severity": "Info",
        }
        require(not close_old or test_id, "关闭旧发现只允许对既有 Test 重导入")
        if commit: data["commit_hash"] = commit
        if build: data["build_id"] = build
        data["test" if test_id else "engagement"] = str(test_id or engagement)
        return self.request(
            "api/v2/reimport-scan/" if test_id else "api/v2/import-scan/",
            method="POST",
            data=data,
            files={"file": (filename, raw, "application/octet-stream")},
        )

    def reportportal_pull(self, project, launch_id):
        require(
            re.fullmatch(r"[a-zA-Z0-9_-]+", project)
            and isinstance(launch_id, int)
            and launch_id > 0,
            "ReportPortal 项目/launch 无效",
        )
        prefix = "api/v1/" + project + "/"
        launch = self.request(prefix + f"launch/{launch_id}")
        require(
            launch.get("id") == launch_id
            and launch.get("status")
            in {"PASSED", "FAILED", "STOPPED", "INTERRUPTED", "CANCELLED", "SKIPPED"},
            "ReportPortal launch 尚未结束或身份不符",
        )
        rows = []
        total = None
        for page in range(1, 1001):
            d = self.request(
                prefix + "item",
                params={
                    "filter.eq.launchId": launch_id,
                    "page.page": page,
                    "page.size": 100,
                },
            )
            meta = d.get("page", {})
            require(
                isinstance(d.get("content"), list) and meta.get("number") == page,
                "ReportPortal 分页不符",
            )
            if total is None:
                total = meta["totalElements"]
            require(total == meta["totalElements"], "ReportPortal 结果变化")
            rows.extend(d["content"])
            if page >= meta["totalPages"]:
                break
        require(
            len(rows) == total and len({x["id"] for x in rows}) == len(rows),
            "ReportPortal 结果缺失/重复",
        )
        return {"launch": launch, "items": rows, "responses": self.raw}

    def sonar_pull(self, project, branch, revision):
        require(
            project and branch and revision, "SonarQube 需要项目、分支和预期 revision"
        )
        p = {"project": project, "branch": branch}
        analyses = self.request("api/project_analyses/search", params={**p, "ps": 1})
        latest = analyses.get("analyses", [])
        require(
            latest and latest[0].get("revision") == revision,
            "SonarQube 最新分析提交与目标不符",
        )
        measures = self.request(
            "api/measures/component",
            params={
                "component": project,
                "branch": branch,
                "metricKeys": "coverage,branch_coverage,duplicated_lines_density,ncloc,bugs,vulnerabilities,code_smells,security_hotspots_reviewed",
            },
        )
        gate = self.request(
            "api/qualitygates/project_status", params={"analysisId": latest[0]["key"]}
        )
        # Recheck after collecting mutable current-component measures.
        after = self.request("api/project_analyses/search", params={**p, "ps": 1})
        require(
            after.get("analyses", [{}])[0].get("key") == latest[0]["key"],
            "SonarQube 分析在拉取期间发生变化",
        )
        return {
            "analysis": latest[0],
            "measures": measures,
            "gate": gate,
            "project": project,
            "branch": branch,
            "responses": self.raw,
        }


def parse_service(raw, kind):
    d = json_data(raw)
    out = base(kind)
    if kind == "defectdojo-api":
        require(
            d.get("test", {}).get("id") and isinstance(d.get("findings"), list),
            "缺少 DefectDojo test/结果",
        )
        for x in d["findings"]:
            # Preserve suppressed/mitigated state; do not discard evidence.
            out["findings"].append(
                finding(
                    str(
                        x.get("vuln_id_from_tool")
                        or x.get("unique_id_from_tool")
                        or x["id"]
                    ),
                    x["title"] + "\n" + x.get("description", ""),
                    x.get("file_path") or "",
                    x.get("line"),
                    x["severity"],
                    external_id=x["id"],
                    active=x.get("active"),
                    verified=x.get("verified"),
                    false_positive=x.get("false_p"),
                    mitigated=x.get("is_mitigated"),
                )
            )
    elif kind == "reportportal":
        launch = d["launch"]
        require(
            launch["status"]
            in {"PASSED", "FAILED", "STOPPED", "INTERRUPTED", "CANCELLED", "SKIPPED"},
            "launch 未结束",
        )
        out["complete"] = launch["status"] in {"PASSED", "FAILED"}
        states = {
            "PASSED": "passed",
            "FAILED": "failed",
            "SKIPPED": "skipped",
            "STOPPED": "error",
            "INTERRUPTED": "error",
            "CANCELLED": "error",
        }
        for x in d["items"]:
            if x.get("hasStats") is False or x.get("type") in {"SUITE", "STORY"}:
                continue
            require(x.get("status") in states, "ReportPortal item 未结束")
            out["tests"].append(
                test(
                    x["name"],
                    states[x["status"]],
                    None,
                    x.get("description", ""),
                    suite=str(x.get("path", x["id"])),
                    external_id=x["id"],
                    issue=x.get("issue"),
                    duration_unavailable=True,
                )
            )
        require(out["tests"], "ReportPortal 无可计数用例")
    elif kind == "sonarqube":
        require(
            d.get("analysis", {}).get("revision")
            and d.get("measures", {}).get("component", {}).get("key")
            == d.get("project"),
            "SonarQube 分析身份不符",
        )
        for m in d["measures"]["component"]["measures"]:
            out["metrics"]["sonar." + m["metric"]] = number(m["value"])
        state = d["gate"]["projectStatus"]["status"]
        require(state in {"OK", "ERROR", "NONE"}, "未知 SonarQube gate")
        out["complete"] = state != "NONE"
        out["tests"].append(
            test(
                "SonarQube Quality Gate",
                {"OK": "passed", "ERROR": "failed", "NONE": "unknown"}[state],
                detail=json.dumps(d["gate"]["projectStatus"].get("conditions", [])),
            )
        )
    return out
