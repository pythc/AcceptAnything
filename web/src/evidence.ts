import type { Artifact, Run } from './types';
export type EvidenceCategory = 'reports' | 'logs' | 'sources' | 'all';
export function evidenceCategory(a: Artifact, sourceRefs: Set<string>): EvidenceCategory {
  if (sourceRefs.has(a.id) || a.name.startsWith('frozen-') || ['source-context.json','remote-source.json','built-image.json'].includes(a.name)) return 'sources';
  if (a.name.endsWith('.log')) return 'logs';
  return 'reports';
}
export function selectEvidence(run: Run, category: EvidenceCategory, query: string, selected: string, refs?: Set<string>) {
  const sourceRefs = new Set([...(run.project_inputs || []).map(x=>x.ref), ...(run.recipe_inputs || []).map(x=>x.ref)]);
  return run.artifacts.filter(a => (!refs || refs.has(a.id)) && (a.id === selected || ((category==='all' || evidenceCategory(a,sourceRefs)===category) && `${a.name} ${a.criterion_id || ''}`.toLowerCase().includes(query.toLowerCase()))));
}
