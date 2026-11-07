"""Real browser calibration: collect state after a failed visual assertion without passing it."""
import json,os,subprocess
from acceptance.engine import ROOT,NODE


def test_visual_failure_retains_final_state_and_failed_actions_still_stop(tmp_path):
    source=ROOT/'acceptance/planning/runtime/browser-support.cjs'
    cases=[]
    for cid,kind in [('visual','expect_visible'),('action','click'),('passed','expect_visible')]:
        cases.append(dict(id=cid,requirement='state',source={},steps=[dict(kind='goto',value='/'),
            dict(kind=kind,selector='#present' if cid=='passed' else '#missing'),
            dict(kind='http',path='/state',method='GET',body=None,status=200,headers={},assertions=[dict(pointer='/status',operator='equals',value='approved')])]))
    plan=tmp_path/'plan.json';plan.write_text(json.dumps(dict(cases=cases)))
    script=tmp_path/'calibrate.cjs'
    script.write_text("""
const http=require('node:http');const assert=require('node:assert/strict');const fs=require('node:fs');
const {chromium,expect}=require(process.env.PW);
(async()=>{
 const server=http.createServer((q,r)=>{r.setHeader('content-type',q.url==='/state'?'application/json':'text/html');r.end(q.url==='/state'?'{"status":"approved"}':'<p id="present">状态</p>');});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));process.env.ACCEPTANCE_BASE='http://127.0.0.1:'+server.address().port;
 const {runCase}=require(process.env.DRIVER);const browser=await chromium.launch({headless:true});
 try{for(const id of ['visual','action','passed']){
   const page=await browser.newPage();page.setDefaultTimeout(200);let failed=false;
   try{await runCase(page,expect.configure({timeout:200}),{},id);}catch(e){failed=true;}
   const trace=JSON.parse(fs.readFileSync(process.env.ACCEPTANCE_OUTPUT+'/'+id+'-trace.json'));
   assert.equal(failed,id!=='passed');assert.equal(trace.status,id==='passed'?'passed':'failed');
   assert.equal(trace.steps.length,id==='action'?2:3);
   if(id!=='action')assert.equal(trace.steps[2].assertions[1].actual,'approved');
   if(id==='visual')assert.equal(trace.steps[1].passed,false);
   await page.close();
 }}finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
""")
    env={**os.environ,'PW':str(ROOT/'validation/node_modules/@playwright/test'),'DRIVER':str(source),
         'ACCEPTANCE_PLAN':str(plan),'ACCEPTANCE_OUTPUT':str(tmp_path),'ACCEPTANCE_RUN':'calibration'}
    result=subprocess.run([str(NODE),str(script)],env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
