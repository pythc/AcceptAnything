from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from acceptance import projects
from acceptance.api import create_app
from acceptance.engine import ROOT, Store, encode, digest
from acceptance.validation import Reader, validate_results


def sample_profile(root, test="import {test} from 'node:test'; test('known', () => {});"):
    root.mkdir()
    (root / "test.mjs").write_text(test)
    (root / "contract.md").write_text("A known check must execute successfully.\n")
    return {"id": "sample", "name": "Sample", "version": "v1", "repository": str(root), "files": ["contract.md", "test.mjs"], "source_path": "contract.md", "source_digest": digest((root / "contract.md").read_bytes()),
            "criteria": [{"id": "KNOWN", "title": "Known check", "expected": "known succeeds", "test_file": "test.mjs", "test_digest": digest((root / "test.mjs").read_bytes()), "source_anchor": "contract.md:1", "test_names": ["known"]}]}


def test_registered_profiles_preserve_large_snapshots_and_all_criteria(tmp_path):
    p=sample_profile(tmp_path/'repo')
    for i in range(515):
        name=f'note-{i}.md';(Path(p['repository'])/name).write_text('source');p['files'].append(name)
    for i in range(2):
        name=f'large-{i}.md';(Path(p['repository'])/name).write_bytes(b'x'*(9*1024*1024));p['files'].append(name)
    p['criteria']=[{**p['criteria'][0],'id':'CHECK_'+str(i)} for i in range(40)]
    store=Store(tmp_path/'store');projects.register(store,p)
    _,files=projects.read_files(projects.profile(store,p['id']))
    assert len(files)==519 and len(projects.profile(store,p['id'])['criteria'])==40
    assert sum(map(len,files.values()))>16*1024*1024


@pytest.fixture(scope="module")
def executed(tmp_path_factory):
    directory = tmp_path_factory.mktemp("project-runs")
    store = Store(directory / "store")
    p = sample_profile(directory / "target")
    projects.register(store, p)
    r = projects.create(store, "sample")
    store.execute(r["id"])
    assert store.snapshot(r["id"])["decision"] == "allow"
    return store, r["id"]


@pytest.mark.parametrize("fault", ["empty", "malformed", "dtd", "no_cases", "duplicate", "wrong_name", "wrong_file", "skipped", "error", "stats", "misplaced_case", "exit", "failure"])
def test_junit_invalid_reports_fail_closed(executed, tmp_path, fault):
    original, rid = executed
    store = Store(tmp_path / "copy")
    shutil.copytree(original.path(rid), store.runs / rid)
    shutil.copytree(original.root / "contracts", store.root / "contracts")
    run = store.read(rid)
    a = next(a for a in run["artifacts"] if a["name"] == "KNOWN-junit.xml")
    raw = store.artifact_bytes(run, a["id"])[1]
    tree = ET.fromstring(raw); suite = tree; case = tree.find("testcase")
    if fault == "empty": raw = b""
    elif fault == "malformed": raw = b"<test"
    elif fault == "dtd": raw = b'<!DOCTYPE testsuites [<!ENTITY x "x">]>' + raw[raw.index(b"<testsuites"):]
    elif fault == "exit": next(c for c in run["commands"] if c["name"] == "node-KNOWN")["exit_code"] = 2
    else:
        if fault == "no_cases": suite.remove(case)
        if fault == "duplicate": suite.append(deepcopy(case))
        if fault == "wrong_name": case.set("name", "unapproved")
        if fault == "wrong_file": case.set("file", "/workspace/unapproved.mjs")
        if fault in ("skipped", "error", "failure"): ET.SubElement(case, fault)
        if fault == "stats":
            tree.remove(case); wrapped = ET.SubElement(tree, "testsuite", tests="0", failures="0", skipped="0", errors="0"); wrapped.append(case)
        if fault == "misplaced_case": tree.remove(case); ET.SubElement(tree, "unknown").append(case)
        raw = ET.tostring(tree)
    (store.path(rid) / "artifacts" / a["file"]).write_bytes(raw)
    a.update(sha256=digest(raw), size=len(raw))
    store.save(run)
    assert store.check_integrity(run)
    assert store.evaluate(run) == "inconclusive"
    view = store.snapshot(rid)
    assert view["decision"] == "inconclusive"
    assert not view["inspections"]["KNOWN"]["verified"]
    assert view["inspections"]["KNOWN"]["actual_value"] is None
    assert TestClient(create_app(store)).get("/api/catalogue").status_code == 200


@pytest.mark.parametrize("fault", ["traversal", "absolute", "hidden", "symlink", "changed_test", "changed_contract", "duplicate_standard"])
def test_registration_rejects_unsafe_or_changed_inputs(tmp_path, fault):
    root = tmp_path / "target"; p = sample_profile(root)
    if fault == "traversal": p["files"].append("../test.mjs")
    if fault == "absolute": p["files"].append(str(root / "test.mjs"))
    if fault == "hidden": (root / ".secret.json").write_text("{}"); p["files"].append(".secret.json")
    if fault == "symlink": (root / "link.mjs").symlink_to(root / "test.mjs"); p["files"].append("link.mjs")
    if fault == "changed_test": (root / "test.mjs").write_text("// no tests")
    if fault == "changed_contract": (root / "contract.md").write_text("new requirements")
    if fault == "duplicate_standard": p["criteria"].append(deepcopy(p["criteria"][0]))
    with pytest.raises(ValueError): projects.register(Store(tmp_path / "store"), p)


def test_offline_runner_real_boundaries_and_timeout(tmp_path, monkeypatch):
    monkeypatch.setenv("ACCEPTANCE_PRIVATE_PROBE", "must-not-enter-container")
    p = sample_profile(tmp_path / "target", """
import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
test('known', () => {
  assert.equal(process.env.ACCEPTANCE_PRIVATE_PROBE, undefined);
  assert.notEqual(process.getuid(), 0);
  assert.equal(fs.existsSync('/var/run/docker.sock'), false);
  assert.throws(() => fs.writeFileSync('/workspace/contract.md', 'overwrite'));
  assert.deepEqual(Object.keys(os.networkInterfaces()), ['lo']);
});
""")
    store = Store(tmp_path / "store"); projects.register(store, p)
    r = projects.create(store, p["id"]); store.execute(r["id"])
    view = store.snapshot(r["id"])
    assert view["decision"] == "allow", view["reasons"]
    before = (Path(p["repository"]) / "contract.md").read_bytes()
    assert digest(before) == p["source_digest"]
    workspace = tmp_path / "timeout-workspace"; workspace.mkdir()
    (workspace / "test.mjs").write_text("setInterval(() => {}, 1000);")
    with pytest.raises(RuntimeError, match="超时"):
        projects.container_command(store, r, r["baseline"]["criteria"][0], workspace, timeout=1)
    name = r["commands"][-1]["argv"][4]
    assert not subprocess.check_output(["docker", "ps", "-aq", "--filter", "name=" + name], text=True).strip()
    assert r["commands"][-1]["truncated"]


def test_historical_project_ignores_current_changes_but_marks_stale(executed, tmp_path):
    original, rid = executed
    store = Store(tmp_path / "copy")
    for name in ("runs", "contracts", "projects"):
        shutil.copytree(original.root / name, store.root / name, dirs_exist_ok=True)
    record = (store.path(rid) / "run.json").read_bytes()
    p = json.loads((store.root / "projects/sample.json").read_bytes())
    p["repository"] = str(tmp_path / "missing-source")
    (store.root / "projects/sample.json").write_bytes(encode(p))
    view = store.snapshot(rid)
    assert view["decision"] == "allow" and not view["applicability"]["matches"]
    assert (store.path(rid) / "run.json").read_bytes() == record


def test_project_api_only_accepts_registered_selection(executed):
    store, rid = executed
    client = TestClient(create_app(store))
    assert client.get("/api/projects").json()[0]["test_count"] == 1
    for body in ({}, {"mode": "fixed", "project_id": "sample"}, {"project_id": "sample", "command": "anything"}):
        assert client.post("/api/runs", json=body).status_code == 422
    assert client.post("/api/runs", json={"project_id": "missing"}).status_code == 404
    assert client.post("/api/runs", json={"project_id": "../escape"}).status_code == 409
