export type Priority = "P0" | "P1" | "P2" | "P3";
type PriorityInput = { priority?: unknown; severity?: unknown };
const suggestions = new Map<string, Priority>([
  ["critical", "P1"],
  ["high", "P1"],
  ["medium", "P2"],
  ["low", "P3"],
  ["info", "P3"],
]);

// A severity-based suggestion is not a completed business-priority triage.
// P0 requires an explicit decision; even critical scanner hits can be unverified.
export function findingPriority(finding: PriorityInput) {
  if (
    typeof finding.priority === "string" &&
    /^P[0-3]$/.test(finding.priority)
  ) {
    return { level: finding.priority as Priority, suggested: false };
  }
  const severity =
    typeof finding.severity === "string"
      ? finding.severity.toLowerCase().trim()
      : "";
  const level = suggestions.get(severity);
  return { level, suggested: !!level };
}
