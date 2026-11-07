import type { Run } from './types';

// Execution completion is independent of the acceptance verdict. A finished
// runner may return errors, skipped tests, or insufficient evidence.
export function executionSummary(run: Run) {
  const planned = new Set(run.baseline.criteria.map(c => c.id));
  const latest = new Map(run.results.map(r => [r.criterion_id, r]));
  const ended = new Set<string>();
  for (const row of run.check_runs ?? []) {
    if (planned.has(row.criterion_id) && row.started_at && row.finished_at)
      ended.add(row.criterion_id);
  }
  for (const [id, row] of latest) {
    if (planned.has(id) && ['passed', 'failed'].includes(row.status)) ended.add(id);
  }
  const results = [...latest.values()].filter(r => planned.has(r.criterion_id));
  return {
    total: planned.size,
    ended: ended.size,
    passed: results.filter(r => r.status === 'passed').length,
    failed: results.filter(r => r.status === 'failed').length,
    uncertain: results.filter(r => ended.has(r.criterion_id) && !['passed', 'failed'].includes(r.status)).length,
    unfinished: planned.size - ended.size,
  };
}
