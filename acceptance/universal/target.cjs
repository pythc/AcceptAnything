const {pathToFileURL}=require('node:url');const path=require('node:path');
(async()=>{const r=JSON.parse(Buffer.from(process.argv[2],'base64').toString());const fs=require('node:fs');const file=path.resolve('/work/repo',r.runtime_entry&&fs.existsSync(path.resolve('/work/repo',r.runtime_entry))?r.runtime_entry:r.module);
if(!file.startsWith('/work/repo/'))throw Error('module outside target');
const exports=await import(pathToFileURL(file).href);const fn=exports[r.function];if(typeof fn!=='function')throw Error('public function unavailable');
const value=await fn(...r.args);if(value===undefined)throw Error('undefined result is not a JSON value');
console.log('\nACCEPTANCE_VALUE:'+JSON.stringify(value));})().catch(e=>{console.error(e.stack);process.exit(2)});
