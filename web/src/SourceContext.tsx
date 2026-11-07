import {
  FolderSimple,
  GitBranch,
  GitCommit,
  Fingerprint,
  ArrowUpRight,
} from "@phosphor-icons/react";
import type { SourceContext } from "./types";

export function revision(source: SourceContext) {
  const repo = source.repository;
  if (repo.commit) return repo.commit.slice(0, 10);
  if (source.provenance === "historical") return "历史未采集";
  return repo.kind === "git" ? "尚无提交" : "本地目录";
}

export function TargetStrip({
  source,
  baseline,
  details,
  repository,
}: {
  source: SourceContext;
  baseline: string;
  details: () => void;
  repository: () => void;
}) {
  const path = source.repository.path;
  const compact = path
    ? "…/" + path.split("/").filter(Boolean).slice(-2).join("/")
    : "未采集";
  return (
    <div className="target-strip console-context">
      <div className="target-meta-line">
        <span>
          <GitBranch size={14} />
          {source.repository.branch ||
            (source.repository.requested_kind === "commit"
              ? "指定提交"
              : "分支未采集")}
        </span>
        <span title={source.repository.commit || undefined}>
          <GitCommit size={14} />
          {revision(source)}
        </span>
        <span>
          {(source.scope.file_count ?? source.scope.files.length)
            ? `${(source.scope.file_count ?? source.scope.files.length)} 个文件`
            : `${source.scope.check_count} 项检查`}
        </span>
        <span title={source.target.environment}>
          {source.target.environment || "环境未采集"}
        </span>
      </div>
      <div className="target-directory-line">
        <span>目录</span>
        <button
          title={path || "历史未采集"}
          onClick={repository}
          disabled={!path}
        >
          {compact}
        </button>
        <button
          className="target-info"
          onClick={details}
          aria-label="查看目标信息"
        >
          目标信息 <ArrowUpRight size={13} />
        </button>
        <span className="target-baseline" title={baseline}>
          基线 {baseline}
        </span>
      </div>
    </div>
  );
}

export function SourceDetails({
  source,
  current = false,
}: {
  source: SourceContext;
  current?: boolean;
}) {
  const repo = source.repository;
  return (
    <div className="source-details">
      {source.provenance === "historical" && (
        <p className="context-note">
          历史执行未采集 Git 元数据。目录来自原命令，未使用当前分支补填。
        </p>
      )}
      <dl className="context-fields">
        <dt>代码仓库</dt>
        <dd>{repo.name}</dd>
        <dt>目录</dt>
        <dd className="path-value">{repo.path || "未采集"}</dd>
        <dt>分支</dt>
        <dd>{repo.branch || (repo.commit ? "分离 HEAD" : "未采集")}</dd>
        <dt>提交</dt>
        <dd>{repo.commit || revision(source)}</dd>
        <dt>远端</dt>
        <dd>
          {repo.remote ||
            (source.provenance === "historical" ||
            repo.remote_configured === undefined
              ? "未采集"
              : repo.remote_configured
                ? "地址未展示"
                : "未配置")}
        </dd>
        <dt>工作区</dt>
        <dd>
          {repo.scoped_changes === null
            ? "未采集"
            : repo.scoped_changes
              ? `验收范围内 ${repo.scoped_changes} 项未提交，其中 ${repo.untracked} 项未跟踪`
              : "验收范围内无未提交改动"}
        </dd>
        <dt>待验对象</dt>
        <dd>
          {source.target.name} ·{" "}
          {(
            {
              buggy: "缺陷版",
              fixed: "修正版",
              project: "项目",
              repository: "代码仓库",
            } as Record<string, string>
          )[source.target.variant] || source.target.variant}
        </dd>
        <dt>环境</dt>
        <dd>
          {source.target.environment}
          {source.target.url && (
            <small>{source.target.url} · 仅执行期间启动</small>
          )}
        </dd>
        <dt>范围</dt>
        <dd>{source.scope.description}</dd>
        <dt>模型</dt>
        <dd>
          {source.provenance === "historical"
            ? "历史未采集"
            : source.tooling.model || "未使用模型"}
        </dd>
        <dt>执行器</dt>
        <dd>
          {source.tooling.executors.join(" / ")}
          {Object.entries(source.tooling.versions).some(([, v]) => v) && (
            <small>
              {Object.entries(source.tooling.versions)
                .filter(([, v]) => v)
                .map(([k, v]) => `${k} ${v}`)
                .join(" · ")}
            </small>
          )}
        </dd>
        <dt>采集时间</dt>
        <dd>
          {source.captured_at
            ? new Date(source.captured_at).toLocaleString("zh-CN", {
                hour12: false,
              })
            : "历史未采集"}
          {current && <small>当前配置；每次新执行会重新采集并封存。</small>}
        </dd>
      </dl>
      <div className="source-file-heading">
        <h4>范围内源文件</h4>
        <span>{(source.scope.file_count ?? source.scope.files.length) || "未采集"}</span>
      </div>
      {source.scope.files.map((file) => (
        <div className="source-file" key={file.path}>
          <strong>{file.path}</strong>
          <small>{file.size.toLocaleString()} bytes</small>
          <code>{file.sha256}</code>
        </div>
      ))}
      <details className="metadata">
        <summary>
          {source.provenance === "historical"
            ? "原目标摘要"
            : "完整文件快照摘要"}
        </summary>
        <code className="context-digest">{source.snapshot.digest}</code>
      </details>
    </div>
  );
}
