// Declarative target-side invocation. Expected values never enter this process.
const fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {pathToFileURL}=require('node:url');
const {spawn}=require('node:child_process');
async function command(argv,input){return new Promise((ok,fail)=>{const p=spawn(argv[0],argv.slice(1),{stdio:['pipe','pipe','pipe']});const out=[],err=[];let timed=false;const timer=setTimeout(()=>{timed=true;p.kill('SIGKILL')},90000);p.stdout.on('data',x=>out.push(x));p.stderr.on('data',x=>err.push(x));p.on('error',e=>{clearTimeout(timer);fail(e)});p.on('close',code=>{clearTimeout(timer);if(timed||code===null)fail(Error('CLI interrupted'));else ok({exit_code:code,stdout:Buffer.concat(out).toString(),stderr:Buffer.concat(err).toString()})});p.stdin.on('error',()=>{});p.stdin.end(input);});}
function member(name){if(typeof name!=='string'||!/^[A-Za-z][A-Za-z0-9_]*$/.test(name)||['constructor','prototype','__proto__'].includes(name))throw Error('private member unavailable');return name;}
function observable(v){
 const handle={observable:false,value:{handle_type:v?.constructor?.name||typeof v}};
 if(v===undefined||typeof v==='function'||typeof v==='symbol')return handle;
 if(v&&typeof v==='object'&&!Array.isArray(v)&&((Object.getPrototypeOf(v)!==Object.prototype&&Object.getPrototypeOf(v)!==null)||Object.values(Object.getOwnPropertyDescriptors(v)).some(d=>typeof d.value==='function')))return handle;
 try{return {observable:true,value:JSON.parse(JSON.stringify(v))};}catch{return handle;}
}
function project(value,pointer){
 if(!pointer.startsWith('/'))throw Error('observation requires a field path');
 for(const part of pointer.slice(1).split('/')){
  const key=part.replace(/~1/g,'/').replace(/~0/g,'~');
  if(['constructor','prototype','__proto__'].includes(key)||key.startsWith('_'))throw Error('private observation unavailable');
  if(value===null||value===undefined||!(key in Object(value)))throw Error('observation unavailable');
  value=value[key];
 }
 return value;
}
async function execute(request,root,onReady){
 root=await fs.realpath(root);
 const state=new Map(),steps=[],cleanup=[],callbacks=[],callbackErrors=[];let failed=false,callbackCount=0;
 const work=await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(),'acceptance-case-')));const previous=process.cwd();process.chdir(work);
 const local=name=>{const p=path.resolve(work,name);if(p!==work&&!p.startsWith(work+path.sep))throw Error('fixture outside case directory');return p;};
 function resolve(v,scope=state){
  if(Array.isArray(v))return v.map(x=>resolve(x,scope));if(!v||typeof v!=='object')return v;
  if('$ref'in v){if(!scope.has(v.$ref))throw Error('reference unavailable');const value=scope.get(v.$ref);return Object.hasOwn(v,'pointer')?project(value,v.pointer):value;}
  if('$path'in v)return local(v.$path);
  if('$callback'in v){
   const cb=v.$callback,captured=new Map(scope),name='acceptance_callback_'+(++callbackCount);
   const begin=args=>{const local=new Map([...captured,...(cb.params||[]).map((p,i)=>[p,args[i]])]);const log={id:name,status:'running',calls:[]};callbacks.push(log);return {local,log};};
   const invoke=(call,local)=>{const owner=local.get(call.target),fn=owner?.[member(call.member)];if(typeof fn!=='function')throw Error('callback public callable unavailable');return Reflect.apply(fn,owner,resolve(call.args||[],local));};
   const save=(call,result,local,log)=>{local.set(call.id,result);log.calls.push({id:call.id,member:call.member,status:'completed',...observable(result)});};
   const finish=(cb,local,log)=>{const result=cb.return_undefined?undefined:resolve(cb.return,local);log.return_value=observable(result);log.status='completed';return result;};
   const sync=(...args)=>{const {local,log}=begin(args);try{for(const call of cb.calls||[])save(call,invoke(call,local),local,log);return finish(cb,local,log);}catch(e){log.status='error';log.error=String(e);callbackErrors.push({log,error:e});throw e;}};
   const asyncFn=async(...args)=>{const {local,log}=begin(args);try{for(const call of cb.calls||[]){let result=invoke(call,local);if(result instanceof Promise||call.await_result)result=await result;save(call,result,local,log);}return finish(cb,local,log);}catch(e){log.status='error';log.error=String(e);callbackErrors.push({log,error:e});throw e;}};
   const fn=cb.async?asyncFn:sync;Object.defineProperty(fn,'name',{value:name});return fn;
  }
  return Object.fromEntries(Object.entries(v).map(([k,x])=>[k,resolve(x,scope)]));
 }
 async function run(s,isCleanup=false){
  if(s.target&&!state.has(s.target))throw Error('prerequisite object unavailable');let v,awaitedTarget;let target=state.get(s.target);
  // Keep configuration-time thenables intact. Resolve a result only when the
  // requested observation is unavailable on the pending wrapper itself.
  const missingMember=['call','observe_call','get'].includes(s.op)&&s.member&&!(s.member in Object(target));
  const pending=target&&typeof target.then==='function';
  let cachedField,hasCachedField=false;
  if(pending&&request.observe_result_fields&&s.op==='get'&&s.member&&!missingMember){cachedField=target[member(s.member)];hasCachedField=true;}
  const pendingField=hasCachedField&&typeof cachedField==='function';
  const missingIterator=s.op==='collect'&&target&&!target[Symbol.iterator]&&!target[Symbol.asyncIterator];
  if(pending&&(missingMember||missingIterator||pendingField)){
   target=await target;state.set(s.target,target);awaitedTarget=s.target;hasCachedField=false;
  }
  if(['call','observe_call'].includes(s.op)){
   let owner,fn;
   if(s.module){const file=path.resolve(root,s.runtime_entry||s.module);if(!file.startsWith(root+path.sep))throw Error('module outside target');owner=await import(pathToFileURL(file).href);fn=owner[member(s.export)];}
   else{owner=target;fn=s.member?owner[member(s.member)]:owner;}
   if(typeof fn!=='function')throw Error('public callable unavailable');const args=resolve(s.args||[]);
   let observedThrow=false;const callbackStart=callbackErrors.length;
   try{
    v=s.instantiate?Reflect.construct(fn,args):Reflect.apply(fn,owner,args);
    // Preserve configuration-time thenables until explicitly requested.
    if(v instanceof Promise||s.await_result)v=await v;
   }catch(e){
    if(s.op!=='observe_call')throw e;
    if(request.observe_callback_errors&&!isCleanup&&e!==null&&['object','function'].includes(typeof e)){
     for(const {log,error} of callbackErrors.slice(callbackStart))if(error===e){log.status='observed-error';log.observed_by=s.id;}
    }
    observedThrow=true;
    v={raised:true,exception:{type:e instanceof Error?e.name:typeof e,message:e instanceof Error?e.message:String(e)}};
   }
   if(s.op==='observe_call'&&!observedThrow){const shown=observable(v);v={raised:false,return_observable:shown.observable,...(shown.observable?{value:shown.value}:{})};}
  }else if(s.op==='get')v=hasCachedField?cachedField:target[member(s.member)];
  else if(s.op==='item'){const key=resolve(s.value);if(['constructor','prototype','__proto__'].includes(key))throw Error('private item unavailable');v=target[key];}
  else if(s.op==='collect'){v=[];for await(const item of target)v.push(item);}
  else if(s.op==='identity'){
   const other=resolve(s.value),handle=x=>x!==null&&['object','function'].includes(typeof x);
   if(!handle(target)||!handle(other))throw Error('identity requires object handles, not scalar values');v=target===other;
  }
  else if(s.op==='inspect_path'){
   if(typeof target!=='string')throw Error('path observation requires a path value');
   const candidate=path.resolve(target),allowed=p=>p===work||p.startsWith(work+path.sep)||p===root||p.startsWith(root+path.sep);
   if(!allowed(candidate))throw Error('path observation outside isolated source and case directories');
   // Resolve existing ancestors too: a missing child of an escaping symlink
   // must not bypass the same boundary applied to an existing path.
   let ancestor=candidate,real;
   for(;;){try{real=await fs.realpath(ancestor);break;}catch(e){if(e.code!=='ENOENT')throw e;const parent=path.dirname(ancestor);if(parent===ancestor)throw e;ancestor=parent;}}
   if(!allowed(real))throw Error('path observation outside isolated source and case directories');
   try{const info=await fs.stat(candidate);v={path:candidate,exists:true,is_file:info.isFile(),is_dir:info.isDirectory()};}
   catch(e){if(e.code!=='ENOENT')throw e;v={path:candidate,exists:false,is_file:false,is_dir:false};}
  }
  else if(s.op==='write_file'){
   const p=local(s.path),encoding=s.encoding||'utf-8',map={'utf-8':'utf8','latin-1':'latin1','ascii':'ascii','base64':'base64'};
   if(!Object.hasOwn(map,encoding))throw Error('unsupported fixture encoding');
   if(['ascii','latin-1'].includes(encoding)&&Array.from(s.value).some(c=>c.codePointAt(0)>(encoding==='ascii'?127:255)))throw Error('fixture outside declared encoding');
   const raw=Buffer.from(s.value,map[encoding]);
   if(encoding==='base64'&&raw.toString('base64')!==s.value)throw Error('noncanonical base64 fixture');
   await fs.mkdir(path.dirname(p),{recursive:true});await fs.writeFile(p,raw);v=p;
  }
  else if(s.op==='cli'){const args=resolve(s.argv||[]);if(!args.every(a=>typeof a==='string'&&!a.includes('\0')))throw Error('CLI arguments must be strings');v=await command([...s.command,...args],s.stdin||'');}
  else throw Error('operation unavailable in JavaScript');
  const selected=(request.observations||[]).filter(o=>o.step===s.id);
  let awaitedResult=false;
  // Builder objects may expose methods with the same name as response fields.
  // A function/opaque handle is not an observation; settle the real result.
  if(v&&typeof v.then==='function'&&selected.some(o=>{try{return !observable(project(v,o.pointer)).observable;}catch{return true;}})){
   v=await v;awaitedResult=true;
  }
  state.set(s.id,v);const row={id:s.id,status:'completed',...observable(v),...(awaitedTarget?{awaited_target:awaitedTarget}:{}),...(awaitedResult?{awaited_result:true}:{})};
  if(!row.observable){
   const observations=selected.map(o=>{
    try{return {pointer:o.pointer,...observable(project(v,o.pointer))};}
    catch(e){return {pointer:o.pointer,observable:false,error:String(e)};}
   });
   if(observations.length)row.observations=observations;
  }
  return row;
 }
 try{
  for(const s of request.steps){if(failed){steps.push({id:s.id,status:'blocked',reason:'prior step failed'});continue;}try{steps.push(await run(s));}catch(e){failed=true;steps.push({id:s.id,status:'error',error:String(e)});}}
  if(onReady&&!failed){try{await onReady(state,work,steps);}catch(e){failed=true;steps.push({id:'managed-session',status:'error',error:String(e)});}}
  for(const s of request.cleanup||[]){try{cleanup.push(await run(s,true));}catch(e){failed=true;cleanup.push({id:s.id,status:'error',error:String(e)});}}
 }finally{process.chdir(previous);await fs.rm(work,{recursive:true,force:true});}
 return {status:failed||callbacks.some(c=>!['completed','observed-error'].includes(c.status))?'error':'completed',steps,cleanup,callbacks,temporary_directory_removed:true};
}
module.exports={execute};
if(require.main===module)execute(JSON.parse(Buffer.from(process.argv[2],'base64').toString()),'/work/repo').then(r=>console.log('\nACCEPTANCE_VALUE:'+JSON.stringify(r))).catch(e=>{console.error(e);process.exitCode=2;});
