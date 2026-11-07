import test from 'node:test';
import assert from 'node:assert/strict';
import {caseForResult,plannedCaseResult} from '../src/plannedResults.ts';
test('OpenAPI native names remain traceable without pretending to be generated function names',()=>{
  const task={id:'schema',state:'completed',report_ref:'raw',report:{tests:[{name:'GET /health',status:'failed',detail:'wrong type'}]}};
  const run={tasks:[task],test_plan:{cases:[{id:'C1',name:'test_C1'}],checks:[{id:'schema',engine:'openapi',case_ids:['C1']}]}};
  assert.equal(caseForResult(run,task,task.report.tests[0]).id,'C1');
  assert.equal(plannedCaseResult(run,'C1').status,'failed');
  assert.match(plannedCaseResult(run,'C1').detail,/wrong type/);
  assert.equal(plannedCaseResult(run,'C1').report_ref,'raw');
});
test('missing, skipped and running cases never become passed',()=>{
  const task={id:'batch',state:'running'};
  const run={tasks:[task],test_plan:{cases:[{id:'C1',name:'test_C1'}],checks:[{id:'batch',engine:'module',case_ids:['C1']}]}};
  assert.equal(plannedCaseResult(run,'C1').status,'running');
  task.state='completed';task.report={tests:[]};assert.equal(plannedCaseResult(run,'C1'),null);
  task.report.tests.push({name:'test_C1',status:'skipped'});assert.equal(plannedCaseResult(run,'C1').status,'skipped');
});
