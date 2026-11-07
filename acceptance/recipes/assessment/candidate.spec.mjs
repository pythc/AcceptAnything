import {test, expect} from '../../../validation/node_modules/@playwright/test/index.mjs';
import {execFileSync} from 'node:child_process';
import {writeFile, readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
const origin=process.env.ACCEPTANCE_URL;
const output=process.env.ACCEPTANCE_REPORT;
const hash=x=>createHash('sha256').update(x).digest('hex');
const password='Acceptance-Candidate-2026';
async function api(request,path,method='GET',data,csrf) {
  const r=await request.fetch(origin+path,{method,data,headers:{Origin:origin,...(csrf?{'X-CSRF-Token':csrf}:{})}});
  expect(r.ok(),`${method} ${path}: ${r.status()} ${await r.text()}`).toBeTruthy();return r.json();
}
async function admin(browser) {
  const context=await browser.newContext();
  const session=await api(context.request,'/api/auth/login','POST',{account:'admin@acceptance.test',password:'Acceptance-Synthetic-Only-2026'});
  return {context,request:context.request,csrf:session.csrfToken};
}
async function mcp(request,token,name,args={}) {
  const response=await request.post(origin+'/mcp',{headers:{Authorization:'Bearer '+token,Accept:'application/json, text/event-stream'},data:{jsonrpc:'2.0',id:1,method:'tools/call',params:{name,arguments:args}}});
  expect(response.status()).toBe(200);const raw=await response.json();expect(raw.error).toBeUndefined();expect(raw.result.isError).not.toBe(true);
  return raw.result.structuredContent ?? JSON.parse(raw.result.content.find(x=>x.type==='text').text);
}
function field(page,id) {return page.locator(`#${id} input, input#${id}`);}

if(process.env.ACCEPTANCE_COMPLETE==='1') {
  test('CANDIDATE-E2E: register, enroll, start, upload unchanged bytes and explicitly finalize',async({page,browser},info)=>{
    const ops=await admin(browser);let enrollmentId;
    const email='candidate-'+process.env.ACCEPTANCE_RUN+'@acceptance.test';
    const suffix=String(parseInt(process.env.ACCEPTANCE_RUN.slice(-8),16)).padStart(10,'0');
    try {
      const {round}=await api(ops.request,'/api/admin/rounds','POST',{name:'候选人验收-'+process.env.ACCEPTANCE_RUN},ops.csrf);
      const {batch}=await api(ops.request,'/api/admin/batches','POST',{roundId:round.id,name:'完整流程验收',description:'合成数据',opensAt:new Date(Date.now()-60000).toISOString(),startClosesAt:new Date(Date.now()+3600000).toISOString(),durationHours:24,status:'OPEN'},ops.csrf);
      const {question}=await api(ops.request,'/api/admin/questions','POST',{batchId:batch.id,direction:'DEVELOPMENT_TEST',title:'独立验收题目',content:'完成本地合成项目验收',published:true,attachmentIds:[]},ops.csrf);
      await test.step('浏览器注册：真实挑战与验证码校验，邮件仅从本地测试发件箱读取',async()=>{
        await page.goto('/register');
        for(const [id,value] of Object.entries({name:'验收同学','student-no':'2026'+suffix.slice(-6),college:'计算机学院',major:'软件工程',phone:'138'+suffix.slice(-8),email,'new-password':password})) await field(page,id).fill(value);
        const sent=page.waitForResponse(r=>r.url().endsWith('/api/auth/email-code')&&r.request().method()==='POST');
        await page.getByRole('button',{name:'发送验证码',exact:true}).click();
        const response=await sent;expect(response.status(),await response.text()).toBe(200);
        expect(email).toMatch(/^[a-z0-9-]+@acceptance\.test$/);
        const mail=execFileSync('docker',['exec',process.env.ACCEPTANCE_DB,'psql','-U','acceptance_test','-d','acceptance_test','-At','-c',`SELECT body FROM acceptance_ui.email_outbox WHERE to_email='${email}' ORDER BY created_at DESC LIMIT 1`],{encoding:'utf8',timeout:10000});
        const code=mail.match(/\b\d{6}\b/)?.[0];expect(code).toBeTruthy();
        await field(page,'code').fill(code);await page.getByRole('checkbox').check();
        await page.getByRole('button',{name:'创建账号',exact:true}).click();await expect(page).toHaveURL(/\/recruitment/);
      });
      await test.step('报名、同意、真实 MCP 预检后从页面开考',async()=>{
        const card=page.locator('article').filter({has:page.getByRole('heading',{name:'完整流程验收',exact:true})});
        await card.getByRole('radio',{name:/开发|测试/}).click();await card.getByRole('button',{name:'报名并准备',exact:true}).click();
        await expect(page).toHaveURL(/\/recruitment\/prepare\//);enrollmentId=page.url().split('/').pop();
        let current=(await api(page.request,`/api/enrollments/${enrollmentId}`)).enrollment;expect(current.question).toBeNull();
        await page.getByRole('checkbox').check();await page.getByRole('button',{name:'同意并继续',exact:true}).click();
        const me=await api(page.request,'/api/auth/me');
        const token=(await api(page.request,`/api/enrollments/${enrollmentId}/mcp-token`,'POST',{},me.csrfToken)).token;
        await mcp(page.request,token,'test_connection');
        await page.reload();await page.getByRole('button',{name:'开始考核',exact:true}).click();
        await page.getByRole('button',{name:'确认开始',exact:true}).click();await expect(page).toHaveURL(/\/recruitment\/exam\//);
        await expect(page.getByRole('heading',{name:question.title,exact:true})).toBeVisible();
        current=(await api(page.request,`/api/enrollments/${enrollmentId}`)).enrollment;expect(current.state).toBe('ACTIVE');
        await info.attach('start-state',{body:Buffer.from(JSON.stringify({state:current.state,startedAt:current.startedAt,deadline:current.deadline,question:current.question.title})),contentType:'application/json'});
      });
      await test.step('网页锁定仓库 SHA，经真实 MCP 和上传助手传输原始二进制',async()=>{
        await field(page,'repo-url').fill('https://github.com/acceptance/local-project');
        await page.getByRole('button',{name:'核对提交版本',exact:true}).click();
        await page.getByRole('button',{name:'确认此版本',exact:true}).click();
        await expect(page.getByText('SHA 已锁定',{exact:true})).toBeVisible();
        const me=await api(page.request,'/api/auth/me');
        // Unsafe repository destinations must fail before the fixture boundary.
        for(const url of ['http://127.0.0.1/admin','https://user:password@github.com/a/b','https://github.com.evil.test/a/b']) {
          const r=await page.request.post(origin+`/api/enrollments/${enrollmentId}/repository/preview`,{headers:{Origin:origin,'X-CSRF-Token':me.csrfToken},data:{url}});
          expect(r.status()).toBe(400);
        }
        const token=(await api(page.request,`/api/enrollments/${enrollmentId}/mcp-token`,'POST',{},me.csrfToken)).token;
        const ticket=await mcp(page.request,token,'submit_materials',{repoSha:'a'.repeat(40),clients:[{name:'验收客户端',models:[{name:'unknown',source:'unknown'}]}],projectSummary:'本地合成验收',collaborationSummary:'传输合成原始文件'});
        const body=Buffer.alloc(65553,0xa5);Buffer.from('验收原始字节\r\n\u0000').copy(body);
        const filename=output+'/native-conversation.bin', ticketfile=output+'/upload-ticket.json';
        await writeFile(filename,body,{mode:0o600});await writeFile(ticketfile,JSON.stringify(ticket),{mode:0o600});
        const helper=await page.request.get(ticket.helperUrl);expect(helper.ok()).toBeTruthy();
        const helperfile=output+'/upload-materials.py';await writeFile(helperfile,await helper.body());
        execFileSync(fileURLToPath(new URL('../../../validation/.venv/bin/python',import.meta.url)),[helperfile,'--ticket-file',ticketfile,'--file',filename,'--snapshot'],{timeout:60000,stdio:'pipe'});
        expect(hash(await readFile(filename))).toBe(hash(body));
        const doc=await api(ops.request,`/api/enrollments/${enrollmentId}/materials`);
        const file=doc.payload.files[0];const downloaded=await ops.request.get(origin+file.downloadUrl);expect(downloaded.ok()).toBeTruthy();expect(hash(await downloaded.body())).toBe(hash(body));
        const denied=await page.request.get(origin+file.downloadUrl);expect(denied.status()).toBe(403);
        await writeFile(output+'/recovery-expected.json',JSON.stringify({enrollmentId,sha:'a'.repeat(40),files:[{url:file.downloadUrl,sha256:hash(body)}]}));
        await page.reload();
      });
      await test.step('候选人显式交卷、刷新持久化、交卷后拒绝修改',async()=>{
        await page.getByRole('button',{name:'确认交卷',exact:true}).click();
        const modal=page.getByRole('dialog');await modal.getByRole('checkbox').check();
        await modal.getByRole('button',{name:'确认交卷',exact:true}).click();
        await expect(page.getByRole('heading',{name:'已交卷',exact:true})).toBeVisible();await page.reload();
        await expect(page.getByRole('heading',{name:'已交卷',exact:true})).toBeVisible();
        const current=(await api(page.request,`/api/enrollments/${enrollmentId}`)).enrollment;
        expect(current.state).toBe('FINALIZED');expect(current.repository.sha).toBe('a'.repeat(40));
        const me=await api(page.request,'/api/auth/me');
        const rejected=await page.request.post(origin+`/api/enrollments/${enrollmentId}/repository/preview`,{headers:{Origin:origin,'X-CSRF-Token':me.csrfToken},data:{url:'https://github.com/acceptance/local-project'}});
        expect([400,403,409]).toContain(rejected.status());
        await info.attach('candidate-finalized',{body:await page.screenshot(),contentType:'image/png'});
      });
    } finally {await ops.context.close();}
  });

  test('BROWSER-SECURITY: unauthenticated access, CSRF, Origin, SQL payload and response headers',async({page,browser},info)=>{
    const checks=[];
    for(const path of ['/api/admin/overview','/api/admin/candidates','/api/admin/audit','/api/admin/export']) {
      const r=await page.request.get(origin+path);expect(r.status()).toBe(401);checks.push({path,status:r.status()});
    }
    const injection=await page.request.post(origin+'/api/auth/login',{headers:{Origin:origin},data:{account:"' OR 1=1 --",password:'SyntheticPassword123'}});
    expect([400,401]).toContain(injection.status());checks.push({case:'SQL-like login payload cannot authenticate',status:injection.status()});
    const ops=await admin(browser);
    try {
      for(const [name,headers] of [['missing CSRF',{Origin:origin}],['wrong CSRF',{Origin:origin,'X-CSRF-Token':'incorrect'}],['foreign Origin',{Origin:'https://attacker.invalid','X-CSRF-Token':ops.csrf}]]) {
        const r=await ops.request.post(origin+'/api/admin/rounds',{headers,data:{name:'must-never-be-created'}});expect(r.status()).toBe(403);checks.push({case:name,status:r.status()});
      }
      const response=await page.request.get(origin+'/login');
      expect(response.headers()['x-content-type-options']).toBe('nosniff');expect(response.headers()['content-security-policy']).toContain("frame-ancestors 'none'");expect(response.headers()['x-frame-options']).toBe('DENY');
      await info.attach('security-probes',{body:Buffer.from(JSON.stringify({checks,headers:response.headers()})),contentType:'application/json'});
    } finally {await ops.context.close();}
  });
}
