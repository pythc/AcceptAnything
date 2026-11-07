import test from 'node:test';
import assert from 'node:assert/strict';
import { pipeline, seconds, clockTime, stageDuration } from '../src/pipeline.ts';

const historical = () => ({baseline:{criteria:[{layer:'L1'}]},status:'completed', decision:'reject', layers:[{id:'L1',status:'failed',count:1,failed:1}],layer_runs:[{layer:'L1',started_at:'2026-10-17T00:00:01Z',finished_at:'2026-10-17T00:00:02Z'}],findings:[{id:'F-001'}],artifacts:[{name:'gate-result.json'}],reasons:['required failure']});

test('historical views preserve recorded layer times without fabricating phase times', () => {
  const run=historical(), before=JSON.stringify(run), stages=pipeline(run);
  assert.equal(stages[0].status,'recorded');
  assert.equal(stages[0].duration_ms,undefined);
  assert.equal(stages[2].started_at,run.layer_runs[0].started_at);
  assert.equal(stages[6].status,'failed');
  assert.equal(stages[6].started_at,undefined);
  assert.equal(JSON.stringify(run),before);
});

test('new interrupted runs do not inherit inferred success for unstarted stages', () => {
  const stages=pipeline({...historical(),status:'error',pipeline:[{id:'L1',status:'error',detail:'executor failed',started_at:'2026-10-17T00:00:01Z'}]});
  assert.equal(stages[2].status,'error');
  assert.equal(stages[3].status,'not_run');
  assert.equal(stages[6].status,'not_run');
});

test('timing distinguishes unknown and sub-centisecond work, and clock includes seconds', () => {
  assert.equal(seconds(undefined),'未记录');
  assert.equal(seconds(0.5),'<0.01 s');
  assert.equal(seconds(1400),'1.4 s');
  assert.match(clockTime('2026-10-17T00:00:01.123Z'),/\d{2}:\d{2}:01[.,]123/);
});

test('recovery time is not reported as measured executor duration', () => {
  const stage={id:'L2',status:'error',detail:'interrupted',started_at:'2026-10-17T00:00:01Z',finished_at:'2026-10-17T02:00:01Z'};
  assert.equal(stageDuration(stage,false),undefined);
  assert.equal(stageDuration({...stage,status:'passed'},true),7200000);
  assert.equal(stageDuration({...stage,duration_ms:250},false),250);
});


test('project pipeline names the actual runner and excludes unplanned layers while running', () => {
  const stages = pipeline({...historical(), project_id:'sample', status:'running', pipeline:[]});
  assert.equal(stages[2].title, '业务回归');
  assert.equal(stages[2].tool, 'L1 · Node.js');
  assert.equal(stages[3].status, 'not_run');
  assert.equal(stages[4].detail, '不在本次验收范围');
});

test('expanded recipe includes recovery and cleanup before final gate without positional assumptions',()=>{
 const stages=pipeline({...historical(), project_id:'expanded', baseline:{recipe:'assessment-v1',criteria:[{layer:'L1'},{layer:'L2'},{layer:'L3'},{layer:'L4'}]},pipeline:[{id:'gate',status:'blocked',detail:'6 incomplete'}]});
 assert.deepEqual(stages.slice(-4).map(x=>x.id),['L4','cleanup','findings','gate']);
 assert.equal(stages.find(x=>x.id==='gate').status,'blocked');
 assert.equal(stages.find(x=>x.id==='L2').tool,'Node / PostgreSQL');
});

test('running pipeline uses the live clock even when the latest persisted duration is zero',()=>{
 const stage={id:'native',status:'running',duration_ms:0,started_at:'2026-10-19T00:00:00Z'};
 assert.equal(stageDuration(stage,false,Date.parse('2026-10-19T00:00:07Z')),7000);
 assert.equal(stageDuration({...stage,status:'passed',duration_ms:6000},false),6000);
});
