"""Capture only the configured acceptance target; never discover other projects."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from urllib.parse import urlsplit, urlunsplit


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def repository_id(path):
    return "repo-" + sha(path.encode())[:16] if path else "unassociated"


def git(root, *args):
    try:
        p = subprocess.run(["git", "-C", str(root), *args], stdin=subprocess.DEVNULL, capture_output=True, timeout=3)
        return p.stdout.decode().strip() if p.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return None


def remote_label(value):
    """Never retain remote credentials, query strings or fragments."""
    if not value:
        return None
    if "://" in value:
        try:
            parts = urlsplit(value)
            if not parts.hostname:
                return None
            return urlunsplit((parts.scheme, parts.hostname + (":" + str(parts.port) if parts.port else ""), parts.path, "", ""))
        except ValueError:
            return None
    if "@" in value and ":" in value.split("@", 1)[0]:
        return None
    match = re.fullmatch(r"(?:[^@/:]+@)?([^@/:]+):(.+)", value)
    return match[1] + ":" + match[2].split("?", 1)[0].split("#", 1)[0] if match else None


def scoped_files(mode):
    return ["validation/fixture.py", f"validation/static-samples/{mode}.py"]


def capture(root, mode, criteria, opa):
    files = []
    for relative in scoped_files(mode):
        raw = (root / relative).read_bytes()
        files.append({"path": relative, "sha256": sha(raw), "size": len(raw)})
    git_root = git(root, "rev-parse", "--show-toplevel")
    path = git_root or str(root)
    branch = git(root, "symbolic-ref", "-q", "--short", "HEAD") if git_root else None
    commit = git(root, "rev-parse", "--verify", "HEAD") if git_root else None
    changes = git(root, "status", "--porcelain=v1", "--untracked-files=all", "--", *scoped_files(mode)) if git_root else None
    statuses = changes.splitlines() if changes else []
    remote = git(root, "config", "--get", "remote.origin.url") if git_root else None
    versions = {}
    for name, relative in [("Playwright", "validation/node_modules/@playwright/test/package.json"), ("axe-core", "validation/node_modules/axe-core/package.json")]:
        try:
            versions[name] = json.loads((root / relative).read_text())["version"]
        except (OSError, ValueError, KeyError):
            versions[name] = None
    return {
        "schema_version": 1, "provenance": "captured", "captured_at": datetime.now(timezone.utc).isoformat(),
        "repository": {"id": repository_id(path), "name": Path(path).name, "path": path, "kind": "git" if git_root else "directory",
                       "branch": branch, "commit": commit, "remote": remote_label(remote), "remote_configured": bool(remote),
                       "scoped_changes": len(statuses) if git_root else None, "untracked": sum(s.startswith("??") for s in statuses) if git_root else None},
        "target": {"name": "本地验收示例", "variant": mode, "kind": "fixture", "environment": "本机 · 临时夹具", "url": "http://127.0.0.1:18891"},
        "scope": {"kind": "files", "description": "HTTP 夹具与静态样本；不代表整个仓库", "files": files, "check_count": len(criteria)},
        "snapshot": {"algorithm": "sha256", "digest": sha(canonical(files))},
        "tooling": {"model": None, "executors": ["Bandit B602", "Playwright", "axe-core"], "versions": versions, "gate": "OPA", "opa_image": opa},
    }


def context(run):
    if run.get("source_context"):
        return run["source_context"]
    # Historical absolute paths are interpreted as strings, never used for I/O.
    root = None
    for command in run.get("commands", []):
        if command.get("name") != "bandit":
            continue
        for arg in command.get("argv", []):
            if isinstance(arg, str) and arg.endswith("/validation/static-samples/" + run["mode"] + ".py"):
                path = PurePosixPath(arg)
                if path.is_absolute():
                    root = str(path.parents[2])
    return {
        "schema_version": 1, "provenance": "historical", "captured_at": None,
        "repository": {"id": repository_id(root), "name": PurePosixPath(root).name if root else "未关联目录", "path": root, "kind": "unknown", "branch": None, "commit": None, "remote": None, "scoped_changes": None, "untracked": None},
        "target": {"name": "本地验收示例", "variant": run["mode"], "kind": "fixture", "environment": "本地夹具（历史记录）", "url": None},
        "scope": {"kind": "files", "description": run["baseline"]["scope"], "files": [], "check_count": len(run["baseline"]["criteria"])},
        "snapshot": {"algorithm": "sha256", "digest": run["target_digest"]},
        "tooling": {"model": None, "executors": sorted({c["executor"] for c in run["baseline"]["criteria"]}), "versions": {}, "gate": None, "opa_image": None},
    }


def matches(source, baseline, mode):
    """Bind captured source bytes to the frozen target, not today's Git HEAD."""
    try:
        files = source["scope"]["files"]
        expected = dict(zip(scoped_files(mode), [baseline["fixture_digest"], baseline["sample_digests"][mode]]))
        return (source["provenance"] == "captured" and source["target"]["variant"] == mode
                and len(files) == len(expected) and {f["path"]: f["sha256"] for f in files} == expected
                and source["snapshot"]["digest"] == sha(canonical(files)))
    except (KeyError, TypeError, ValueError):
        return False
