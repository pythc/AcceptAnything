import test from 'node:test';
import assert from 'node:assert/strict';
import { executionSummary } from '../src/executionSummary.ts';

test('finished runner with skipped/unknown coverage is counted without changing verdict',()=>{
 const run={baseline:{criteria:[{id:'native'},{id:'business'}]},results:[{criterion_id:'native',status:'error'},{criterion_id:'business',status:'passed'}],check_runs:[{criterion_id:'native',started_at:'2026-10-25T00:00:00Z',finished_at:'2026-10-25T00:01:00Z'}],decision:'inconclusive'};
 const frozen=JSON.stringify(run);
 assert.deepEqual(executionSummary(run),{total:2,ended:2,passed:1,failed:0,uncertain:1,unfinished:0});
 assert.equal(JSON.stringify(run),frozen);
});
test('queued, running and never started blocked tasks are not completed',()=>{
 const run={baseline:{criteria:[{id:'a'},{id:'b'},{id:'c'}]},results:[{criterion_id:'c',status:'error'}],check_runs:[{criterion_id:'b',status:'running',started_at:'2026-10-25T00:00:00Z',finished_at:null}]};
 assert.deepEqual(executionSummary(run),{total:3,ended:0,passed:0,failed:0,uncertain:0,unfinished:3});
});
test('historical measured verdicts and repeated attempts count a criterion once',()=>{
 const run={baseline:{criteria:[{id:'a'},{id:'b'}]},results:[{criterion_id:'a',status:'failed'},{criterion_id:'a',status:'passed'},{criterion_id:'b',status:'failed'},{criterion_id:'outside',status:'passed'}]};
 assert.deepEqual(executionSummary(run),{total:2,ended:2,passed:1,failed:1,uncertain:0,unfinished:0});
});
