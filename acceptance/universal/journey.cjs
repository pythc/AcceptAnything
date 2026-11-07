// Trusted Playwright assertions. Target sessions receive no expected values.
const fs=require('node:fs/promises'),path=require('node:path');
const {isDeepStrictEqual}=require('node:util');
function pointer(value,p){if(!p)return value;if(!p.startsWith('/'))throw Error('invalid JSON Pointer');for(const key of p.slice(1).split('/').map(x=>x.replace(/~1/g,'/').replace(/~0/g,'~'))){if(value==null||!Object.hasOwn(Object(value),key))throw Error('response field unavailable: '+p);value=value[key];}return value;}
async function run(request,pw){
 const {chromium,expect}=pw,base=new URL(request.base);const vars=Object.create(null),rows=[],network=[];
 const folder=request.output;await fs.mkdir(folder,{recursive:true});let context,browser,page,status='passed';const dialogs=[];
 function url(value){const u=new URL(value,base);if(u.origin!==base.origin)throw Error('browser request outside target origin');return u.href;}
 function input(value){if(typeof value==='string')return value.replace(/\$\{([A-Za-z][A-Za-z0-9_]*)(:[^}]*)?\}/g,(_,key,field)=>{if(!Object.hasOwn(vars,key))throw Error('capture unavailable: '+key);const v=pointer(vars[key],field?field.slice(1):'');if(!['string','number','boolean'].includes(typeof v))throw Error('capture must select a scalar');return String(v);});if(Array.isArray(value))return value.map(input);if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,input(v)]));return value;}
 // Unsupported keywords/formats must error, never silently become true.
 const ajv=new (require(request.ajv||'ajv/dist/2020'))({strict:false,strictSchema:true,allErrors:true});
 try{
  browser=await chromium.launch({headless:true});
  context=await browser.newContext({serviceWorkers:'block',recordHar:{path:path.join(folder,'network.har'),content:request.self_contained_har?'embed':'attach',mode:'full'}});
  await context.tracing.start({screenshots:true,snapshots:true,sources:true});
  await context.route('**/*',route=>{const u=new URL(route.request().url());return u.origin===base.origin||u.protocol==='data:'?route.continue():route.abort('blockedbyclient');});
  await context.routeWebSocket('**/*',socket=>socket.close());
  page=await context.newPage();page.on('console',m=>network.push({kind:'console',type:m.type(),text:m.text()}));page.on('pageerror',e=>network.push({kind:'pageerror',message:String(e)}));page.on('requestfailed',q=>network.push({kind:'requestfailed',url:q.url(),failure:q.failure()}));
  for(const s of request.steps){
   const start=Date.now(),row={id:s.id,action:s.action,input:s,started_at:new Date(start).toISOString()};let asserting=false;
   try{
    const timeout=s.timeout_ms||10000;page.setDefaultTimeout(timeout);const e=expect.configure({timeout});const loc=s.selector?page.locator(s.selector):null;
    if(s.action==='goto'){const r=await page.goto(url(input(s.path)),{waitUntil:'domcontentloaded',timeout});row.actual={url:page.url(),status:r?.status()};}
    else if(s.action==='fill')await loc.fill(String(input(s.value)));
    else if(s.action==='click')await loc.click();
    else if(s.action==='press')await loc.press(String(input(s.value)));
    else if(s.action==='select')await loc.selectOption(input(s.value));
    else if(s.action==='check')await loc.check();
    else if(s.action==='uncheck')await loc.uncheck();
    else if(s.action==='dialog'){const pending={step:s.id,response:s.value,handled:false};dialogs.push(pending);page.once('dialog',async d=>{pending.type=d.type();pending.message=d.message();try{await d[s.value]();pending.handled=true;}catch(e){pending.error=String(e);}});}
    else if(s.action==='expect_text'){
     // Locator text matching deliberately skips <head>. Preserve the requested
     // title oracle and use Playwright's page-title assertion instead.
     const count=await loc.count();if(count>1){row.gap_category='case';throw Error('页面文本定位器不唯一：'+s.selector+'；匹配 '+count+' 个元素');}
     const pageTitle=/^(?:head(?:\s*>\s*|\s+))?title$/.test(s.selector.trim())||(count===1&&await loc.evaluate(el=>el.localName==='title'&&el.parentElement?.localName==='head'));
     asserting=true;
     if(pageTitle){row.assertion_adapter='Playwright.PageAssertions.toHaveTitle';const expected=s.comparison==='contains'?new RegExp(s.expected.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')):s.expected;await e(page).toHaveTitle(expected);row.actual=[await page.title()];}
     else{if(s.comparison==='contains')await e(loc).toContainText(s.expected);else await e(loc).toHaveText(s.expected);row.actual=await loc.allTextContents();}
    }
    else if(s.action==='expect_visible'){asserting=true;await e(loc).toBeVisible({visible:s.expected});row.actual=await loc.isVisible();}
    else if(s.action==='expect_hidden'){asserting=true;if(s.expected!==true)throw Error('expect_hidden requires true');await e(loc).toBeHidden();row.actual=await loc.isHidden();}
    else if(s.action==='expect_url'){asserting=true;const expected=url(s.expected);await e(page).toHaveURL(expected);row.actual=page.url();}
    else if(s.action==='expect_value'){asserting=true;await e(loc).toHaveValue(s.expected);row.actual=await loc.inputValue();}
    else if(s.action==='expect_count'){asserting=true;await e(loc).toHaveCount(s.expected);row.actual=await loc.count();}
    else if(s.action==='expect_attribute'){asserting=true;await e(loc).toHaveAttribute(s.attribute,s.expected);row.actual=await loc.getAttribute(s.attribute);}
    else if(s.action==='expect_validity'){asserting=true;await e.poll(()=>loc.evaluate(el=>({valid:el.validity.valid,valueMissing:el.validity.valueMissing,typeMismatch:el.validity.typeMismatch,rangeUnderflow:el.validity.rangeUnderflow,rangeOverflow:el.validity.rangeOverflow}))).toMatchObject(s.expected);row.actual=await loc.evaluate(el=>({valid:el.validity.valid,valueMissing:el.validity.valueMissing,typeMismatch:el.validity.typeMismatch,rangeUnderflow:el.validity.rangeUnderflow,rangeOverflow:el.validity.rangeOverflow}));}
    else if(['request','poll'].includes(s.action)){
     if((s.action==='poll'||request.assert_requests&&s.expected!==null&&s.expected!==undefined)&&s.pointer&&!['status','headers','value'].includes(s.pointer.split('/')[1])){row.gap_category='case';throw Error('HTTP回执定位须从/status、/headers或/value开始；原输入未改写：'+s.pointer);}
     async function fetch(){try{const r=await context.request.fetch(url(input(s.path)),{maxRedirects:0,headers:input(s.headers||{}),method:s.method||'GET',...(s.form?{form:input(s.form)}:s.body!==null&&s.body!==undefined?{data:input(s.body)}:{}),timeout});const text=await r.text();let value;try{value=JSON.parse(text);}catch{value=text;}const result={status:r.status(),headers:r.headers(),value};await r.dispose();row.transport_error=null;return result;}catch(e){row.transport_error=String(e);throw e;}}
     if(s.action==='poll'){
      const validator=s.comparison==='json_schema'?ajv.compile(s.expected):null;
      asserting=true;await e.poll(async()=>{row.actual=await fetch();let v;try{v=pointer(row.actual,s.pointer);row.observation_error=null;}catch(err){row.observation_error=String(err);throw err;}if(validator)return validator(v);if(s.comparison==='contains')return typeof v==='string'||Array.isArray(v)?v.includes(s.expected):false;return isDeepStrictEqual(v,s.expected);},{intervals:[100,250,500]}).toBe(true);
     }else{
      row.actual=await fetch();
      if(request.assert_requests&&s.expected!==null&&s.expected!==undefined){
       const validator=s.comparison==='json_schema'?ajv.compile(s.expected):null;const actual=pointer(row.actual,s.pointer);asserting=true;
       if(validator)expect(validator(actual),JSON.stringify(validator.errors)).toBe(true);
       else if(s.comparison==='contains')expect(actual).toContain(s.expected);
       else expect(actual).toEqual(s.expected);
      }
     }
     if(s.capture)vars[s.capture]=row.actual;
    }else throw Error('unknown browser action');
    row.status='passed';
   }catch(err){
    row.error=String(err);
    if(row.error.includes('strict mode violation'))row.gap_category='case';
    row.status=asserting&&err.matcherResult&&!row.transport_error&&!row.observation_error&&!row.gap_category?'failed':'error';
    try{row.observed={url:page.url(),...(s.selector?{count:await page.locator(s.selector).count(),text:await page.locator(s.selector).allTextContents()}:{}),body:await page.locator('body').innerText()};}catch(e){row.observation_error=String(e);}
    status=row.status;
   }
   row.duration_ms=Date.now()-start;rows.push(row);
   try{await page.screenshot({path:path.join(folder,s.id+'.png'),fullPage:true,timeout:10000});row.screenshot=s.id+'.png';}catch(err){row.screenshot_error=String(err);}
   await fs.writeFile(path.join(folder,'steps.json'),JSON.stringify(rows,null,2));if(row.status!=='passed')break;
  }
 }catch(err){status='error';rows.push({id:'browser-driver',status:'error',error:String(err)});}
 finally{
  if(context){try{await context.tracing.stop({path:path.join(folder,'trace.zip')});}catch(e){status='error';rows.push({id:'trace-close',status:'error',error:String(e)});}await context.close();}
  if(browser)await browser.close();await fs.writeFile(path.join(folder,'browser-events.json'),JSON.stringify(network,null,2));
 }
 if(status==='passed'&&dialogs.some(d=>!d.handled||d.error))status='error';
 const result={status,steps:rows,dialogs,engine:'Playwright',fresh_context:true,origin:base.origin};const errors=rows.filter(r=>r.status==='error');if(errors.length&&errors.every(r=>r.gap_category==='case'))result.gap_category='case';await fs.writeFile(path.join(folder,'receipt.json'),JSON.stringify(result,null,2));return result;
}
module.exports={run};
if(require.main===module)fs.readFile(process.argv[3],'utf8').then(JSON.parse).then(q=>run(q,require(process.argv[2]))).then(r=>console.log('\nACCEPTANCE_VALUE:'+JSON.stringify(r))).catch(e=>{console.error(e);process.exitCode=2;});
