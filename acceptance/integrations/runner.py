"""Frozen file scope, immutable image IDs, bounded disposable Docker executions."""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import selectors
import signal
import subprocess
import time
import uuid
from .formats import require, parse
from .registry import TOOLS, ROOT


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode()


class CapturedFiles:
    def __init__(self,paths):self.paths=paths
    def __getitem__(self,key):return self.paths[key].read_bytes()
    def __iter__(self):return iter(self.paths)
    def __len__(self):return len(self.paths)


def collect(repository, files):
    root = Path(repository).resolve(strict=True)
    require(root.is_dir(), "仓库路径不存在")
    captured = {}
    for relative in files:
        part = PurePosixPath(relative)
        require(
            isinstance(relative, str)
            and not part.is_absolute()
            and ".." not in part.parts
            and str(part) == relative
            and "\\" not in relative,
            "文件路径不规范",
        )
        path = root / relative
        require(
            all(not p.is_symlink() for p in [path, *path.parents] if p != root.parent),
            "不接受符号链接",
        )
        require(
            path.resolve().is_relative_to(root)
            and path.is_file(),
            "文件越界或不是普通文件",
        )
        captured[relative] = path
    return root, CapturedFiles(captured)


def frozen_source(repository, files, output):
    root, captured = collect(repository, files)
    manifest = []
    import shutil
    from .storage import file_digest
    for name, origin in sorted(captured.paths.items()):
        path=output/name;path.parent.mkdir(parents=True,exist_ok=True)
        with origin.open('rb') as src,path.open('wb') as dst:shutil.copyfileobj(src,dst,1024*1024)
        mode=origin.stat().st_mode&0o777;path.chmod(mode)
        manifest.append(dict(path=name,sha256=file_digest(path),size=path.stat().st_size,mode=mode))

    def git(*args):
        result = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else None

    return dict(
        repository=str(root),
        revision=git("rev-parse", "HEAD") or "uncommitted",
        branch=git("branch", "--show-current"),
        snapshot_digest=sha(encode(manifest)),
        files=manifest,
    )


def invoke(argv, timeout, directory, cancelled=lambda: False, container=None, extra_env=None):
    started = time.monotonic()
    size = 0
    reason = None
    proc = subprocess.Popen(
        argv,
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**{
            k: v
            for k, v in os.environ.items()
            if k
            in {
                "PATH",
                "HOME",
                "DOCKER_HOST",
                "DOCKER_CONTEXT",
                "DOCKER_CONFIG",
                "TMPDIR",
            }
        }, **(extra_env or {})},
    )
    streams = {name:(directory/(name+'.log')).open('wb') for name in ('stdout','stderr')}
    with selectors.DefaultSelector() as selector:
        selector.register(proc.stdout, selectors.EVENT_READ, "stdout")
        selector.register(proc.stderr, selectors.EVENT_READ, "stderr")
        while selector.get_map():
            if cancelled():
                reason = "cancelled"
            elif time.monotonic() - started > timeout:
                reason = "timeout"
            if reason:
                if container:
                    subprocess.run(
                        ["docker", "rm", "-f", container],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=15,
                    )
                try: os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            for key, _ in selector.select(0.1):
                data = os.read(key.fileobj.fileno(), 65536)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                size += len(data)
                streams[key.data].write(data);streams[key.data].flush()
            if reason and proc.poll() is not None:
                break
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try: os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        proc.wait()
    for stream in streams.values():stream.close()
    return {
        "argv": argv,
        "exit_code": proc.returncode,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "interruption": reason,
    }, (directory/"stdout.log").read_bytes()


def execute(task, source, output, image, cancelled):
    spec = TOOLS[task.tool]
    if task.tool.startswith('gmah-'):
        from ..planning.gmah import execute_native
        command, _ = execute_native(task, source, output, cancelled)
        (output/'command.json').write_bytes(encode(command))
        require(command['interruption'] is None, '测试中断：'+str(command['interruption']))
        require(command['exit_code'] in spec['exit_codes'], '执行器异常退出：'+str(command['exit_code']))
        report=parse(spec['format'], (output/spec['report']).read_bytes())
        failures=any(t['status'] in {'failed','error'} for t in report['tests'])
        require((command['exit_code']!=0)==failures, '原生执行结果与报告不一致')
        return report,command
    require(
        image and image.startswith("sha256:"), "执行器缺少固定镜像；先运行 provision"
    )
    require(task.network == "none" or spec["registry_network"], "此执行器不允许外网")
    require(
        not spec["registry_network"] or task.network == "registry",
        "依赖数据库/注册表扫描需要明确 registry 网络",
    )
    require((source / task.target).exists(), "执行目标不在冻结快照中")
    require(
        task.target == "."
        or (source / task.target).resolve().is_relative_to(source.resolve()),
        "执行目标越界",
    )
    output.mkdir(parents=True, exist_ok=True)
    name = "acceptance-int-" + uuid.uuid4().hex[:12]
    common = [
        "docker",
        "run",
        "--name",
        name,
        "--label",
        "acceptance.integration=true",
        "--label",
        "acceptance.run=" + source.parent.name,
        "--network",
        "bridge" if task.network == "registry" else "none",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--read-only",
        "--memory",
        "1536m",
        "--cpus",
        "2",
        "--pids-limit",
        "256",
        "--tmpfs",
        "/tmp:rw,nosuid,size=536870912",
        "--env",
        "HOME=/tmp",
        "--env",
        "XDG_CACHE_HOME=/tmp/cache",
        "--env",
        "COVERAGE_FILE=/output/.coverage",
        "--env",
        "SEMGREP_SEND_METRICS=off",
        "--env",
        "SYFT_CHECK_FOR_APP_UPDATE=false",
        "--env",
        "GRYPE_CHECK_FOR_APP_UPDATE=false",
        "--env",
        "CHECKOV_SKIP_PACKAGE_SCAN=true",
        "--workdir",
        "/source",
        "--mount",
        f"type=bind,src={source},dst=/source,readonly",
        "--mount",
        f"type=bind,src={output},dst=/output",
        image,
    ]
    if task.tool in {"trivy-fs", "grype"}:
        cache = ROOT / "var/integrations/cache" / spec["image_key"]
        cache.mkdir(parents=True, exist_ok=True)
        common[-1:-1] = [
            "--env",
            "GRYPE_DB_CACHE_DIR=/cache/grype",
            "--env",
            "XDG_CACHE_HOME=/cache",
            "--mount",
            f"type=bind,src={cache},dst=/cache",
        ]
    common[-1:-1] = [
        "--mount",
        f"type=bind,src={source.parent / 'recipes'},dst=/recipe,readonly",
    ]
    args = [
        s.replace(
            "{target}", "/source" if task.target == "." else "/source/" + task.target
        )
        for s in spec["argv"]
    ]
    if task.service_script:
        require(spec["image_key"] in {"python", "node"}, "该镜像不支持内部目标进程")
        require((source / task.service_script).is_file(), "目标服务脚本不在冻结快照中")
        runtime = "python" if spec["image_key"] == "python" else "node"
        wrapper = (
            source.parent
            / "recipes"
            / ("with-service.py" if runtime == "python" else "with-service.cjs")
        )
        common[-1:-1] = [
            "--mount",
            f"type=bind,src={wrapper},dst=/acceptance-service,readonly",
        ]
        args = [runtime, "/acceptance-service", "/source/" + task.service_script, *args]
    # Wait for Docker create to reach a known daemon state before cancellation
    # can kill the attached client. Killing `docker run` during creation races
    # with daemon creation and can leave an orphan after an early rm.
    create=[*common];create[1]='create'
    try:
        if cancelled():raise ValueError('工具中断：cancelled')
        created=subprocess.run(create+args,capture_output=True,timeout=30)
        require(created.returncode==0,'容器创建失败：'+created.stderr.decode(errors='replace')[-500:])
        command, stdout = invoke(['docker','start','-a',name], task.timeout, output, cancelled, name)
        command['creation_argv']=create+args
    finally:
        subprocess.run(
            ["docker", "rm", "-f", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
    (output / "command.json").write_bytes(encode(command))
    require(
        command["interruption"] is None, "工具中断：" + str(command["interruption"])
    )
    require(
        command["exit_code"] in spec["exit_codes"],
        "工具退出异常：" + str(command["exit_code"]),
    )
    if spec["report"] == "stdout":
        raw = stdout
        (
            output / "report.json"
            if spec["format"] != "junit"
            else output / "report.xml"
        ).write_bytes(raw)
    elif spec["report"] == "allure":
        paths = sorted((output / "allure").glob("*-result.json"))
        require(paths, "Allure 缺少结果文件")
        raw = encode([json.loads(p.read_bytes()) for p in paths])
        (output / "report.json").write_bytes(raw)
    else:
        path = output / spec["report"]
        require(
            path.is_file()
            and not path.is_symlink(),
            "原始报告缺失",
        )
        raw = path.read_bytes()
    if task.tool in {"trivy-fs", "grype"}:
        db_files = [p for p in cache.rglob("*") if p.is_file() and not p.is_symlink()]
        metadata = []
        for db in db_files:
            if db.suffix not in {".db", ".json"}:
                continue
            h = hashlib.sha256()
            with db.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(chunk)
            metadata.append(
                {
                    "path": str(db.relative_to(cache)),
                    "sha256": h.hexdigest(),
                    "size": db.stat().st_size,
                }
            )
        (output / "database-manifest.json").write_bytes(encode(metadata))
    normalized = parse(spec["format"], raw)
    # Exit status must agree with actual findings for tools with a reliable 0/1 contract.
    if task.tool in {
        "bandit",
        "ruff",
        "gitleaks",
        "semgrep",
        "semgrep-njsscan",
        "eslint",
        "hadolint",
        "shellcheck",
    }:
        require(
            command["exit_code"] == (1 if normalized["findings"] else 0),
            "报告与退出码不一致",
        )
    if task.tool in {"pytest", "pytest-allure", "node-test", "newman"}:
        failures = any(t["status"] in {"failed", "error"} for t in normalized["tests"])
        require(
            command["exit_code"] == (1 if failures else 0), "测试退出码与报告不一致"
        )
    return normalized, command
