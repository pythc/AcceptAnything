const fs=require('node:fs');
const path=require('node:path');
const {isDeepStrictEqual}=require('node:util');
const plan=JSON.parse(fs.readFileSync(process.env.ACCEPTANCE_PLAN,'utf8'));
const base=process.env.ACCEPTANCE_BASE;
function resolve(value,vars){
  if(Array.isArray(value))return value.map(v=>resolve(v,vars));
  if(value && typeof value==='object')return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,resolve(v,vars)]));
  if(typeof value!=='string')return value;
  const full=value.match(/^\$\{([A-Za-z][A-Za-z0-9_-]*)\}$/);
  if(full)return vars[full[1]];
  return value.replace(/\$\{([A-Za-z][A-Za-z0-9_-]*)\}/g,(_,key)=>String(vars[key]));
}
function redact(value){
  if(Array.isArray(value))return value.map(redact);
  if(value && typeof value==='object')return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,/password|token|secret|authorization|cookie/i.test(k)?'[redacted]':redact(v)]));
  return value;
}
function pointer(value,p){for(const part of p?p.split('/').slice(1):[])value=value[part.replaceAll('~1','/').replaceAll('~0','~')];return value;}
exports.runCase=async(page,expect,info,cid)=>{
  const c=plan.cases.find(x=>x.id===cid), trace={case_id:cid,requirement:c.requirement,source:c.source,steps:[],status:'error'};
  const vars={run_id:process.env.ACCEPTANCE_RUN+'-'+cid};
  const started=Date.now();
  await page.context().route('**/*',route=>new URL(route.request().url()).origin===base ? route.continue() : route.abort());
  await page.routeWebSocket('**/*',ws=>ws.close());
  try {
    for(const original of c.steps){
      const s=resolve(original,vars),row={input:redact(s),started_at:new Date().toISOString(),assertions:[]};trace.steps.push(row);
      const t=Date.now();
      try{
        if(s.kind==='http'){
          if(!s.path.startsWith('/') || s.path.startsWith('//') || /[\\\r\n#]/.test(s.path) || new URL(base+s.path).origin!==base)throw Error('接口路径越过隔离目标');
          const response=await page.context().request.fetch(base+s.path,{method:s.method,headers:s.headers,...(s.body!==null?{data:s.body}:{}),maxRedirects:0,timeout:5000});
          try{
            const raw=await response.body();if(raw.length>1048576)throw Error('响应超过 1 MiB');
            let data;try{data=JSON.parse(raw.toString());}catch{data=raw.toString();}
            row.response={status:response.status(),body:redact(data)};
            const status={pointer:'HTTP status',operator:'equals',expected:s.status,actual:response.status(),passed:response.status()===s.status};row.assertions.push(status);
            expect(status.actual).toBe(status.expected);
            for(const a of s.assertions){
              const actual=pointer(data,a.pointer), expected=a.value;
              const passed=a.operator==='equals'?isDeepStrictEqual(actual,expected):a.operator==='contains'&&(typeof actual==='string'?typeof expected==='string'&&actual.includes(expected):Array.isArray(actual)&&actual.some(v=>isDeepStrictEqual(v,expected)));
              row.assertions.push({pointer:a.pointer,operator:a.operator,expected:redact(expected),actual:redact(actual),passed});
              expect(passed,`${cid} 接口断言 ${a.pointer}`).toBe(true);
            }
            for(const [key,p] of Object.entries(s.capture||{}))vars[key]=pointer(data,p);
          }finally{await response.dispose();}
        }else if(s.kind==='goto')await page.goto(base+s.value);
        else if(s.kind==='fill')await page.locator(s.selector).fill(s.value);
        else if(s.kind==='click')await page.locator(s.selector).click();
        else if(s.kind==='check')await page.locator(s.selector).check();
        else{
          const a={pointer:s.selector||'URL',operator:s.kind,expected:s.kind==='expect_visible'?true:s.kind==='expect_url'?base+s.value:s.value,actual:null,passed:false};row.assertions.push(a);
          try{
            if(s.kind==='expect_text')await expect(page.locator(s.selector)).toHaveText(s.value);
            else if(s.kind==='expect_visible')await expect(page.locator(s.selector)).toBeVisible();
            else if(s.kind==='expect_url')await expect(page).toHaveURL(base+s.value);
            else throw Error('未知浏览器步骤');
            a.passed=true;
          }finally{
            a.actual=s.kind==='expect_url'?page.url():s.kind==='expect_visible'?await page.locator(s.selector).isVisible().catch(()=>false):await page.locator(s.selector).innerText({timeout:500}).catch(()=>null);
          }
        }
        row.passed=true;
      }catch(e){
        row.passed=false;row.error=e.message.slice(0,3000);
        // Keep read-only page assertion failures, then collect the remaining
        // business-state evidence. Failed actions/HTTP prerequisites still stop.
        if(!s.kind.startsWith('expect_'))throw e;
        await page.screenshot({path:path.join(process.env.ACCEPTANCE_OUTPUT,cid+'-step-'+trace.steps.length+'-failed.png'),fullPage:true}).catch(()=>{});
      }
      finally{row.duration_ms=Date.now()-t;row.finished_at=new Date().toISOString();}
    }
    const failures=trace.steps.filter(s=>s.passed===false);
    if(failures.length)throw Error(failures.map(s=>s.error).join('\n'));
    trace.status='passed';
  }catch(e){trace.status='failed';trace.error=e.message.slice(0,5000);throw e;}
  finally{
    trace.duration_ms=Date.now()-started;
    await page.screenshot({path:path.join(process.env.ACCEPTANCE_OUTPUT,cid+'.png'),fullPage:true}).catch(()=>{});
    fs.writeFileSync(path.join(process.env.ACCEPTANCE_OUTPUT,cid+'-trace.json'),JSON.stringify(trace,null,2));
  }
};
