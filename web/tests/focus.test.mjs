import test from 'node:test';
import assert from 'node:assert/strict';
import { focusChecks, acceptanceVerdict } from '../src/focus.ts';

test('focus preserves failures, skipped and missing mandatory checks; only passed rows collapse', () => {
  const run = { status: 'completed', baseline: { criteria: ['pass','missing','failed','skip','error'].map(id=>({id,required:true})) },
    results: [{criterion_id:'pass',status:'passed'}, {criterion_id:'failed',status:'failed'},
      {criterion_id:'skip',status:'skipped'}, {criterion_id:'error',status:'error'}] };
  const original=JSON.stringify(run);
  const rows=focusChecks(run);
  assert.deepEqual(rows.attention.map(r=>r.criterion.id),['failed','error','missing','skip']);
  assert.deepEqual(rows.completed.map(r=>r.criterion.id),['pass']);
  assert.equal(rows.all.length,5);
  assert.equal(JSON.stringify(run),original);
});
test('a finished or nominally allowed run with incomplete coverage never appears passed', () => {
  assert.equal(acceptanceVerdict({status:'completed',decision:'allow',completion:{complete:false}}).title,'验收未完成');
  assert.equal(acceptanceVerdict({status:'completed',decision:'inconclusive'}).label,'无法下结论');
  assert.equal(acceptanceVerdict({status:'running',decision:'allow'}).label,'尚未判定');
  assert.equal(acceptanceVerdict({status:'completed',decision:'allow',completion:{complete:true,kind:'scoped'}}).title,'所选范围验收通过');
});
