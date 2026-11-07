import { useEffect, useRef, type ReactNode } from "react";
import { findingPriority } from "./priority";
import {
  Check,
  WarningCircle,
  SpinnerGap,
  Minus,
  X,
} from "@phosphor-icons/react";
export const labels: Record<string, string> = {
  allow: "所选基线通过",
  reject: "未通过",
  inconclusive: "无法下结论",
  passed: "通过",
  failed: "失败",
  error: "执行异常",
  blocked: "未完成",
  not_run: "未执行",
  skipped: "已跳过",
  running: "执行中",
  queued: "等待执行",
  incomplete: "验收未完成",
  completed: "执行结束",
};
export const severity: Record<string, string> = {
  critical: "严重",
  high: "高",
  medium: "中",
  low: "低",
  info: "提示",
};
export function PriorityBadge({
  finding,
}: {
  finding: { priority?: unknown; severity?: unknown };
}) {
  const priority = findingPriority(finding);
  return (
    <span
      className={
        "priority-badge " + (priority.level?.toLowerCase() || "unrated")
      }
      title={
        priority.suggested
          ? "按原始严重度建议，尚未完成人工优先级评估；P0 需明确确认"
          : priority.level
            ? "已记录的处理优先级"
            : "缺少分级依据"
      }
    >
      {priority.level || "待分级"}
      {priority.suggested && <small>建议</small>}
    </span>
  );
}
export function StateIcon({ status }: { status: string }) {
  return (
    <span className={"state-icon " + status}>
      {status === "passed" ? (
        <Check />
      ) : status === "failed" || status === "error" ? (
        <WarningCircle />
      ) : status === "running" ? (
        <SpinnerGap className="spin" />
      ) : (
        <Minus />
      )}
    </span>
  );
}
export function Modal({
  title,
  close,
  children,
}: {
  title: string;
  close: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return (
    <dialog
      ref={ref}
      className="modal"
      aria-label={title}
      onCancel={close}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div className="modal-header">
        <h3>{title}</h3>
        <button className="icon-button" onClick={close} aria-label="关闭">
          <X size={23} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
