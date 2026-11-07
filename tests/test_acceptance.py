from copy import deepcopy
import json
from pathlib import Path
import threading
import shutil
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from acceptance import engine
from acceptance.engine import Store, baseline, encode
from acceptance.api import create_app


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path)


_recordings = {}


@pytest.fixture(scope="session", autouse=True)
def actual_report_fixtures(tmp_path_factory):
    source = Store(tmp_path_factory.mktemp("actual-components"))
    for mode in ("fixed", "buggy"):
        with source.lease():
            run = source.create(mode)
            source.execute(run["id"])
        view = source.snapshot(run["id"])
        assert view["decision"] == ("allow" if mode == "fixed" else "reject"), view["reasons"]
        _recordings[mode] = source.path(run["id"])


def prepared(store, mode="fixed"):
    path = _recordings[mode]
    shutil.copytree(path, store.runs / path.name)
    run = store.read(path.name)
    run["decision"] = "inconclusive"
    store.save(run)
    return run


def test_allow_complete_baseline(store):
    r = prepared(store)
    assert store.evaluate(r) == "allow"


def rewrite_report(store, run, name, transform):
    item = next(a for a in run["artifacts"] if a["name"] == name)
    old = json.loads(store.artifact_bytes(run, item["id"])[1])
    data = encode(transform(old))
    (store.path(run["id"]) / "artifacts" / item["file"]).write_bytes(data)
    item.update(size=len(data), sha256=engine.digest(data))
    return item


@pytest.mark.parametrize("fault", ["empty", "missing_results", "null_results", "missing_errors", "zero_files", "wrong_target", "suppressed", "skipped", "exit_code"])
def test_bandit_invalid_evidence_never_allows_even_with_matching_hash(store, fault):
    r = prepared(store)
    def damage(report):
        target = next(k for k in report["metrics"] if k != "_totals")
        if fault == "empty": return {}
        if fault == "missing_results": report.pop("results")
        if fault == "null_results": report["results"] = None
        if fault == "missing_errors": report.pop("errors")
        if fault == "zero_files": report["metrics"] = {"_totals": {"loc": 0}}
        if fault == "wrong_target": report["metrics"]["/another/target.py"] = report["metrics"].pop(target)
        if fault == "suppressed": report["metrics"][target]["nosec"] = 1
        if fault == "skipped": report["metrics"][target]["skipped_tests"] = 1
        if fault == "exit_code": next(c for c in r["commands"] if c["name"] == "bandit")["exit_code"] = 2
        return report
    rewrite_report(store, r, "bandit.json", damage)
    r["decision"] = "allow"; store.save(r)
    assert store.check_integrity(r)  # Correct hashes do not make a report valid.
    assert store.evaluate(r) == "inconclusive"
    view = store.snapshot(r["id"])
    assert view["recorded_decision"] == "allow" and view["decision"] == "inconclusive"
    assert not view["inspections"]["SEC-SHELL"]["verified"]
    assert next(x for x in view["results"] if x["criterion_id"] == "SEC-SHELL")["status"] == "error"
    client = TestClient(create_app(store))
    assert "结论：无法下结论" in client.get(f"/api/runs/{r['id']}/report").text
    assert client.get("/api/runs").json()[0]["decision"] == "inconclusive"


@pytest.mark.parametrize("fault", ["empty", "no_tests", "duplicate", "expected_failure", "retry", "skipped", "stats", "suite_error", "envelope_mismatch"])
def test_playwright_report_requires_complete_original_observations(store, fault):
    r = prepared(store)
    def damage(raw):
        if fault == "empty": return {}
        if fault == "no_tests": raw["suites"] = []; return raw
        spec = next(engine.flatten(raw["suites"]))
        if fault == "duplicate": raw["suites"][0]["specs"].append(deepcopy(spec))
        if fault == "expected_failure": spec["tests"][0]["expectedStatus"] = "failed"
        if fault == "retry": spec["tests"][0]["results"][0]["retry"] = 1
        if fault == "skipped": spec["tests"][0]["results"][0]["status"] = "skipped"
        if fault == "stats": raw["stats"]["expected"] = 0
        if fault == "suite_error": raw["errors"] = [{"message": "beforeAll failed"}]
        if fault == "envelope_mismatch": spec["tests"][0]["results"][0]["duration"] += 1
        return raw
    rewrite_report(store, r, "playwright-L2-results.json", damage)
    assert store.check_integrity(r)
    assert store.evaluate(r) == "inconclusive"


def test_historical_decision_survives_current_contract_and_source_change(store, monkeypatch, tmp_path):
    r = prepared(store); r["decision"] = "allow"; store.save(r)
    old_bytes = (store.path(r["id"]) / "run.json").read_bytes()
    changed = baseline(); changed["version"] = "next-version"
    monkeypatch.setattr(engine, "baseline", lambda: changed)
    suite = tmp_path / "changed.mjs"; suite.write_text("changed source")
    monkeypatch.setattr(engine, "SUITE", suite)
    view = store.snapshot(r["id"])
    assert view["decision"] == "allow" and view["integrity"]
    assert not view["applicability"]["matches"]
    assert (store.path(r["id"]) / "run.json").read_bytes() == old_bytes


def test_one_broken_record_does_not_hide_valid_history(store):
    r = prepared(store)
    bad = store.runs / "run-000000000007"; bad.mkdir(); (bad / "run.json").write_text("{broken")
    rows = store.list()
    assert len(rows) == 2 and any(x["id"] == r["id"] for x in rows)
    assert next(x for x in rows if x["id"] == bad.name)["record_error"]
    assert (bad / "run.json").read_text() == "{broken"
    assert TestClient(create_app(store)).get("/api/repositories").status_code == 200


def test_evidence_read_once_per_snapshot(store):
    r = prepared(store)
    with patch.object(store, "artifact_bytes", wraps=store.artifact_bytes) as read:
        store.snapshot(r["id"])
    assert read.call_count == len(r["artifacts"])


def test_reject_business_failure(store):
    r = prepared(store, "buggy")
    assert store.evaluate(r) == "reject"


@pytest.mark.parametrize("status", ["skipped", "error", "blocked", "not_run", "unsupported", "needs_review", "not_applicable"])
def test_non_success_cannot_allow(store, status):
    r = prepared(store)
    r["results"][0]["status"] = status
    assert store.evaluate(r) == "inconclusive"


@pytest.mark.parametrize("change", ["missing", "duplicate", "no_evidence", "foreign_evidence", "incomplete", "target", "suite", "baseline"])
def test_gate_rejects_invalid_inputs(store, change):
    r = prepared(store)
    if change == "missing": r["results"].pop()
    elif change == "duplicate": r["results"].append(deepcopy(r["results"][0]))
    elif change == "no_evidence": r["results"][0]["evidence_refs"] = []
    elif change == "foreign_evidence": r["results"][0]["evidence_refs"] = ["art-from-another-run"]
    elif change == "incomplete": r["status"] = "error"
    elif change == "target": r["target_digest"] = "wrong"
    elif change == "suite": r["suite_digest"] = "wrong"
    elif change == "baseline": r["baseline"]["criteria"][0]["expected"] = "relaxed expectation"
    assert store.evaluate(r) == "inconclusive"


def test_artifact_tamper_blocks_download_and_old_verdict(store):
    r = prepared(store)
    r["decision"] = "allow"; store.save(r)
    a = r["artifacts"][0]
    (store.path(r["id"]) / "artifacts" / a["file"]).write_text("tampered")
    with pytest.raises(ValueError): store.artifact_bytes(r, a["id"])
    assert store.snapshot(r["id"])["decision"] == "inconclusive"
    assert store.list()[0]["decision"] == "inconclusive"
    assert store.read(r["id"])["decision"] == "allow"  # Derived views never overwrite the old record.


def test_record_tamper_detected(store):
    r = prepared(store); path = store.path(r["id"]) / "run.json"
    raw = json.loads(path.read_text()); raw["record"]["decision"] = "allow"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError): store.read(r["id"])


def test_frozen_standard_tamper(monkeypatch, tmp_path, store):
    source = tmp_path / "changed.json"; source.write_bytes(engine.BASELINE.read_bytes() + b" ")
    source.with_suffix(".sha256").write_text(engine.BASELINE.with_suffix(".sha256").read_text())
    monkeypatch.setattr(engine, "BASELINE", source)
    with pytest.raises(ValueError): store.create("fixed")


@pytest.mark.parametrize("field,value", [("case_id", "wrong-case"), ("expected", "relaxed"), ("layer", "L4")])
def test_results_bound_to_frozen_semantics(store, field, value):
    r = prepared(store)
    r["results"][0][field] = value
    assert store.evaluate(r) == "inconclusive"


def test_same_run_unrelated_evidence_not_accepted(store):
    r = prepared(store)
    r["results"][0]["evidence_refs"] = r["results"][1]["evidence_refs"]
    assert store.evaluate(r) == "inconclusive"


def test_tool_error_retains_observed_failures(store):
    r = store.create("buggy")
    original = store.command
    def fail_after_static(run, label, argv, **kwargs):
        if label.startswith("playwright"):
            raise RuntimeError("simulated executor unavailable")
        return original(run, label, argv, **kwargs)
    with patch.object(store, "command", side_effect=fail_after_static):
        store.execute(r["id"])
    v = store.read(r["id"])
    assert v["decision"] == "inconclusive"
    assert v["status"] == "error"
    assert v["findings"][0]["criterion_id"] == "SEC-SHELL"


def test_incomplete_static_report_is_not_a_confirmed_finding(store):
    r = store.create("buggy")
    def incomplete(run, label, argv, **kwargs):
        if label != "bandit": raise RuntimeError("stop after static probe")
        output = Path(argv[-1])
        output.write_text(json.dumps({"results": [{"test_id": "B602"}], "errors": [{"reason": "file read failed"}]}))
        ref = store.artifact(run, "bandit.log", b"incomplete scan", media_type="text/plain")
        return 1, ref
    with patch.object(store, "command", side_effect=incomplete):
        store.execute(r["id"])
    actual = store.snapshot(r["id"])
    assert actual["decision"] == "inconclusive"
    assert actual["results"][0]["status"] == "error"
    assert actual["findings"] == []


def test_completed_execution_cannot_be_rerun_in_place(store):
    r = prepared(store)
    before = (store.path(r["id"]) / "run.json").read_bytes()
    with pytest.raises(ValueError, match="历史执行只读"):
        store.execute(r["id"])
    assert (store.path(r["id"]) / "run.json").read_bytes() == before


@pytest.mark.parametrize("run_id", ["../standards", "run-../../etc/passwd", "run-deadbeef0000"])
def test_path_traversal_and_unknown_run(store, run_id):
    with pytest.raises(FileNotFoundError): store.read(run_id)


def test_artifact_symlink_not_served(store, tmp_path):
    r = prepared(store); a = r["artifacts"][0]
    p = store.path(r["id"]) / "artifacts" / a["file"]
    outside = tmp_path / "unrelated"; outside.write_bytes(p.read_bytes()); p.unlink(); p.symlink_to(outside)
    with pytest.raises(ValueError): store.artifact_bytes(r, a["id"])


def test_leases_and_recovery(store):
    r = store.create("fixed")
    with store.lease():
        with pytest.raises(RuntimeError): store.lease()
    store.recover(); r = store.read(r["id"])
    assert r['status']=='queued'
    r['status']='running';store.save(r)
    store.recover(); r = store.read(r['id'])
    assert r["status"] == "error" and r["decision"] == "inconclusive"


def test_executor_timeout_is_bounded_and_logged(store):
    r = store.create("fixed")
    with pytest.raises(RuntimeError, match="执行超时"):
        store.command(r, "timeout-probe", [sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.03)
    assert r["commands"][0]["exit_code"] != 0
    assert r["commands"][0]["argv"][0] == sys.executable
    assert r["commands"][0]["started_at"] <= r["commands"][0]["finished_at"]
    assert any(a["name"] == "timeout-probe.log" for a in r["artifacts"])


def test_api_boundaries_and_download(store):
    r = prepared(store); client = TestClient(create_app(store))
    assert client.get("/api/baseline").json()["version"] == baseline()["version"]
    assert client.post("/api/runs", json={"mode": "remote"}).status_code == 422
    assert client.post("/api/runs", json={"mode": "fixed", "target": "https://example.com"}).status_code == 422
    assert client.post("/api/runs", json={"mode": "fixed"}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/runs", content="{}", headers={"Content-Type": "text/plain"}).status_code == 415
    assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 403
    assert client.get("/api/runs/"+r["id"]+"/report").status_code == 200
    a = r["artifacts"][0]
    response = client.get(f"/api/runs/{r['id']}/artifacts/{a['id']}")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert client.get(f"/api/runs/{r['id']}/artifacts/unregistered").status_code == 404


def test_valid_start_and_durable_queue(store):
    from acceptance.jobs import Jobs
    client = TestClient(create_app(store))
    first = client.post("/api/runs", json={"mode": "fixed"})
    second = client.post("/api/runs", json={"mode": "buggy"})
    assert first.status_code == second.status_code == 202
    jobs = Jobs(store.root / "jobs")
    assert len(jobs.list(active=True)) == 2
    assert store.read(first.json()['id'])['status'] == 'queued'
    assert store.read(second.json()['id'])['status'] == 'queued'
    # HTTP process restart keeps consumer-owned queued attempts intact.
    with TestClient(create_app(store)) as restarted:
        assert restarted.get('/api/runs/'+first.json()['id']).json()['job']['state'] == 'queued'
    assert client.post('/api/jobs/'+second.json()['job_id']+'/cancel',json={}).status_code == 200
    assert store.read(second.json()['id'])['status'] == 'cancelled'


def test_report_connects_decision_checks_and_original_evidence(store):
    r = prepared(store)
    r["decision"] = store.evaluate(r)
    store.save(r)
    client = TestClient(create_app(store))
    report = client.get(f"/api/runs/{r['id']}/report").text
    for value in (r["baseline"]["source"], r["baseline"]["scope"], r["baseline"]["digest"], r["suite_digest"], r["baseline"]["policy_digest"], "gate-input.json", "gate-result.json"):
        assert value in report
    for result in r["results"]:
        assert result["case_id"] in report and result["expected"] in report
        assert result["actual"] in report
        for ref in result["evidence_refs"]:
            assert f"http://testserver/api/runs/{r['id']}/artifacts/{ref}?download=true" in report
    for artifact in r["artifacts"]:
        assert artifact["sha256"] in report and artifact["file"] in report


def test_report_and_history_refuse_stale_allow_after_artifact_change(store):
    r = prepared(store)
    r["decision"] = store.evaluate(r)
    store.save(r)
    artifact = r["artifacts"][0]
    (store.path(r["id"]) / "artifacts" / artifact["file"]).write_bytes(b"changed")
    client = TestClient(create_app(store))
    assert client.get("/api/runs").json()[0]["decision"] == "inconclusive"
    assert "结论：无法下结论" in client.get(f"/api/runs/{r['id']}/report").text


@pytest.mark.parametrize("mode,decision,findings", [("buggy", "reject", 7), ("fixed", "allow", 0)])
def test_actual_components(store, mode, decision, findings):
    r = store.create(mode)
    save = store.save
    def checkpoint(run):
        if run["status"] == "completed":
            assert run["finished_at"] is not None  # No terminal checkpoint before final timing/integrity.
        save(run)
    with patch.object(store, "save", side_effect=checkpoint):
        with store.lease(): store.execute(r["id"])
    actual = store.snapshot(r["id"])
    assert actual["status"] == "completed", actual["reasons"]
    assert actual["decision"] == decision
    assert len(actual["results"]) == 8
    assert len(actual["findings"]) == findings
    assert actual["integrity"]
    assert actual["layers"][-1]["status"] == "not_run"
    stages = actual["layer_runs"]
    assert [s["layer"] for s in stages] == ["L1", "L2", "L3"]
    assert all(stages[i]["finished_at"] <= stages[i+1]["started_at"] for i in range(2))
    phases = actual["pipeline"]
    assert [p["id"] for p in phases] == ["baseline", "cases", "L1", "L2", "L3", "findings", "gate"]
    assert all(p["finished_at"] >= p["started_at"] and p["duration_ms"] >= 0 for p in phases)
    assert all(phases[i]["finished_at"] <= phases[i+1]["started_at"] for i in range(6))
    assert phases[-1]["status"] == ("failed" if mode == "buggy" else "passed")
    assert all(d["verified"] for d in actual["inspections"].values())
    assert len(actual["inspections"]) == 8
    if mode == "buggy":
        assert "静态" in actual["inspections"]["SEC-SHELL"]["limitation"]
        assert actual["inspections"]["A11Y-LABEL"]["actual_value"] == "1 个控件缺少名称"
    for name, relative in [("bandit.json", "bandit.json"), ("playwright-L2-results.json", "L2/results.json"), ("playwright-L3-results.json", "L3/results.json")]:
        artifact = next(a for a in actual["artifacts"] if a["name"] == name)
        assert store.artifact_bytes(actual, artifact["id"])[1] == (store.path(r["id"]) / "execution" / relative).read_bytes()


def test_pipeline_checkpoint_is_live_and_failure_is_closed(store):
    r = store.create("fixed")
    with pytest.raises(RuntimeError):
        with store.stage(r, "L2", "request validation"):
            live = store.snapshot(r["id"])
            assert live["pipeline"][0]["status"] == "running"
            assert live["pipeline"][0]["finished_at"] is None
            raise RuntimeError("executor unavailable")
    phase = store.read(r["id"])["pipeline"][0]
    assert phase["status"] == "error" and phase["finished_at"] >= phase["started_at"]
    assert phase["duration_ms"] >= 0 and phase["detail"] == "executor unavailable"


def test_recovery_closes_active_pipeline_without_inventing_duration(store):
    r = store.create("fixed")
    r.update(status="running", active_layer="L2", pipeline=[{"id": "L2", "status": "running", "started_at": r["created_at"], "finished_at": None}])
    store.save(r); store.recover()
    record = store.read(r["id"])
    assert record["pipeline"][0]["status"] == "error"
    assert record["pipeline"][0]["finished_at"] == record["finished_at"]
    assert "duration_ms" not in record["pipeline"][0]
    assert record["active_layer"] is None


def assertion_record(store, cid="SEC-IDOR", line=20, expected="403", actual="200"):
    r = prepared(store, "buggy")
    result = next(x for x in r["results"] if x["criterion_id"] == cid)
    artifact = next(a for a in r["artifacts"] if a["name"] == cid + "-result.json")
    report = json.loads(store.artifact_bytes(r, artifact["id"])[1])
    original = next(a for a in r["artifacts"] if a["id"] == report["source_report"])
    raw = json.loads(store.artifact_bytes(r, original["id"])[1])
    error = {"message": f"Expected: {expected}\nReceived: {actual}", "location": {"file": str(engine.SUITE), "line": line}, "snippet": "exact source snippet"}
    report["result"]["error"] = error
    report["result"]["errors"] = [error]
    spec = next(x for x in engine.flatten(raw["suites"]) if x["title"].split(":", 1)[0] == cid)
    spec["tests"][0]["results"][0] = deepcopy(report["result"])
    for item, value in [(artifact, report), (original, raw)]:
        data = encode(value)
        (store.path(r["id"]) / "artifacts" / item["file"]).write_bytes(data)
        item.update(sha256=engine.digest(data), size=len(data))
    store.save(r)
    return r, artifact["id"], original["id"]


def test_finding_projection_connects_exact_observation_and_original_report(store):
    r, ref, original = assertion_record(store)
    before = (store.path(r["id"]) / "run.json").read_bytes()
    detail = store.snapshot(r["id"])["inspections"]["SEC-IDOR"]
    assert detail["verified"] and detail["actual_value"] == "200" and detail["expected_value"] == "403"
    assert detail["primary_ref"] == ref and detail["source_report"] == original
    assert "Alice" in detail["summary"] and "200" in detail["summary"]
    assert detail["snippet"] == "exact source snippet"
    assert "正文" in detail["limitation"]
    assert (store.path(r["id"]) / "run.json").read_bytes() == before


def test_early_assertion_failure_does_not_invent_later_product_outcome(store):
    r, _, _ = assertion_record(store, "REQ-IDEMPOTENCY", line=33, expected="201", actual="400")
    detail = store.snapshot(r["id"])["inspections"]["REQ-IDEMPOTENCY"]
    assert detail["actual_value"] == "400"
    assert "不同的订单" not in detail["summary"]
    assert "断言失败" in detail["summary"]


def test_corrupted_artifact_cannot_become_a_readable_confirmed_fact(store):
    r, ref, _ = assertion_record(store)
    a = next(a for a in r["artifacts"] if a["id"] == ref)
    (store.path(r["id"]) / "artifacts" / a["file"]).write_text("corrupted")
    detail = store.snapshot(r["id"])["inspections"]["SEC-IDOR"]
    assert not detail["verified"] and detail["actual_value"] is None
    assert "200" not in detail["summary"]


def test_fixture_case_narratives_are_bound_to_known_frozen_suite(store):
    r, _, _ = assertion_record(store)
    r["suite_digest"] = "another-suite"
    store.save(r)
    assert store.snapshot(r["id"])["inspections"] == {}


def test_missing_axe_violations_is_unknown_not_zero_violations(store):
    r, _, _ = assertion_record(store, "A11Y-LABEL", line=44, expected="[]", actual="[object]")
    ref = store.artifact(r, "axe-result.json", b'{}', "A11Y-LABEL", "application/json")
    next(x for x in r["results"] if x["criterion_id"] == "A11Y-LABEL")["evidence_refs"].append(ref)
    store.save(r)
    detail = store.snapshot(r["id"])["inspections"]["A11Y-LABEL"]
    assert not detail["verified"] and detail["actual_value"] is None
    assert "snippet" not in detail


def test_relative_data_root_is_normalized_before_executor_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    relative = Store(Path("relative-data"))
    r = relative.create("buggy")
    assert relative.root == tmp_path / "relative-data"
    assert relative.path(r["id"]).is_absolute()


def test_captured_source_has_exact_scoped_manifest_and_not_fake_revision(store):
    r = store.create("buggy")
    from acceptance import source
    ctx = r["source_context"]
    assert ctx["provenance"] == "captured" and ctx["captured_at"]
    assert source.matches(ctx, r["baseline"], "buggy")
    assert {f["path"] for f in ctx["scope"]["files"]} == {"validation/fixture.py", "validation/static-samples/buggy.py"}
    assert ctx["scope"]["check_count"] == 8
    assert ctx["tooling"]["model"] is None
    assert ctx["repository"]["commit"] is None or len(ctx["repository"]["commit"]) in (40, 64)


def test_stored_git_context_is_not_refreshed_on_history_read(store):
    r = store.create("fixed")
    before = (store.path(r["id"]) / "run.json").read_bytes()
    with patch("acceptance.source.git", side_effect=AssertionError("history must not query git")):
        view = store.snapshot(r["id"])
    assert view["source"] == r["source_context"]
    assert (store.path(r["id"]) / "run.json").read_bytes() == before


def test_old_execution_metadata_stays_unknown_without_modifying_record(store):
    r = store.create("fixed"); r.pop("source_context"); store.save(r)
    before = (store.path(r["id"]) / "run.json").read_bytes()
    ctx = store.snapshot(r["id"])["source"]
    assert ctx["provenance"] == "historical"
    assert ctx["repository"]["branch"] is None and ctx["repository"]["commit"] is None
    assert not ctx["scope"]["files"] and ctx["captured_at"] is None
    assert (store.path(r["id"]) / "run.json").read_bytes() == before


def test_source_snapshot_tamper_cannot_reuse_old_allow(store):
    r = prepared(store); r["decision"] = "allow"
    r["source_context"]["scope"]["files"][0]["sha256"] = "changed"
    store.save(r)
    assert store.snapshot(r["id"])["decision"] == "inconclusive"
    assert store.evaluate(r) == "inconclusive"


@pytest.mark.parametrize("value, expected", [
    ("https://user:synthetic-password@example.test/project.git?token=synthetic#fragment", "https://example.test/project.git"),
    ("git@example.test:team/project.git", "example.test:team/project.git"),
    ("user:synthetic-password@example.test:project.git", None),
])
def test_remote_metadata_drops_credentials(value, expected):
    from acceptance.source import remote_label
    assert remote_label(value) == expected


def test_git_repository_without_a_commit_is_reported_truthfully(tmp_path):
    import subprocess
    from acceptance.source import capture
    subprocess.run(["git", "init", "-b", "main", str(tmp_path)], check=True, capture_output=True)
    (tmp_path / "validation/static-samples").mkdir(parents=True)
    (tmp_path / "validation/fixture.py").write_text("fixture")
    (tmp_path / "validation/static-samples/fixed.py").write_text("sample")
    ctx = capture(tmp_path, "fixed", [], engine.OPA)
    assert ctx["repository"]["kind"] == "git"
    assert ctx["repository"]["branch"] == "main"
    assert ctx["repository"]["commit"] is None
    assert ctx["repository"]["scoped_changes"] == 2 and ctx["repository"]["untracked"] == 2


def test_repository_catalogue_and_target_api_preserve_scope(store):
    r = prepared(store)
    client = TestClient(create_app(store))
    target = client.get("/api/target?mode=buggy").json()
    assert target["target"]["variant"] == "buggy"
    assert len(target["scope"]["files"]) == 2
    groups = client.get("/api/repositories").json()
    assert len(groups) == 1 and groups[0]["run_count"] == 1
    assert groups[0]["latest"]["id"] == r["id"]
    assert groups[0]["latest"]["check_count"] == 8
    report = client.get(f"/api/runs/{r['id']}/report").text
    assert "## 仓库与版本" in report and r["source_context"]["snapshot"]["digest"] in report
