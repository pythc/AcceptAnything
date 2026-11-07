import test from 'node:test';
import assert from 'node:assert/strict';
import {selectEvidence} from '../src/evidence.ts';
const run={project_inputs:[{path:'src/private.ts',ref:'src'}],recipe_inputs:[{path:'runner.py',ref:'runner'}],artifacts:[{id:'report',name:'C-raw.json',criterion_id:'C'},{id:'src',name:'private.ts'},{id:'runner',name:'runner.py'},{id:'log',name:'C.log'},{id:'gate',name:'gate-result.json'}]};
test('default evidence does not mix source and infrastructure logs with reports',()=>{
 assert.deepEqual(selectEvidence(run,'reports','','').map(x=>x.id),['report','gate']);
 assert.deepEqual(selectEvidence(run,'sources','','').map(x=>x.id),['src','runner']);
 assert.deepEqual(selectEvidence(run,'logs','','').map(x=>x.id),['log']);
});
test('direct evidence link remains visible and finding scope never leaks unrelated artifacts',()=>{
 assert.deepEqual(selectEvidence(run,'reports','','src').map(x=>x.id),['report','src','gate']);
 assert.deepEqual(selectEvidence(run,'all','','src',new Set(['report','log'])).map(x=>x.id),['report','log']);
 assert.deepEqual(selectEvidence(run,'all','C-raw','').map(x=>x.id),['report']);
});
