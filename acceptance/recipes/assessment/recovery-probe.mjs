import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
const expected=JSON.parse(await readFile(process.env.ACCEPTANCE_EXPECTED));
const base=process.env.ACCEPTANCE_URL;
const login=await fetch(base+'/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json',Origin:base},body:JSON.stringify({account:'admin@acceptance.test',password:'Acceptance-Synthetic-Only-2026'}),signal:AbortSignal.timeout(15000)});
assert.equal(login.status,200);
const cookie=login.headers.getSetCookie().map(c=>c.split(';')[0]).join('; ');
const response=await fetch(base+`/api/admin/enrollments/${expected.enrollmentId}`,{headers:{Cookie:cookie},signal:AbortSignal.timeout(15000)});
assert.equal(response.status,200);const detail=await response.json();assert.equal(detail.enrollment.state,'FINALIZED');assert.equal(detail.enrollment.repository.sha,expected.sha);
let verified=0;
for(const file of expected.files){
  const r=await fetch(base+file.url,{headers:{Cookie:cookie},signal:AbortSignal.timeout(15000)});assert.equal(r.status,200);
  assert.equal(createHash('sha256').update(Buffer.from(await r.arrayBuffer())).digest('hex'),file.sha256);verified++;
}
console.log(JSON.stringify({state:detail.enrollment.state,sha:detail.enrollment.repository.sha,files:expected.files.length,verified_files:verified}));
