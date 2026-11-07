// Target-side module bridge. This process never receives the acceptance oracle.
const http=require('node:http');
const {pathToFileURL}=require('node:url');
const path=require('node:path');
const root='/source';
http.createServer(async(req,res)=>{
  res.setHeader('content-type','application/json');
  if(req.url==='/health'){res.end('{"status":"ok"}');return;}
  if(req.method!=='POST'||req.url!=='/call'){res.writeHead(404).end('{}');return;}
  let raw='';
  try{
    for await(const chunk of req){raw+=chunk;if(Buffer.byteLength(raw)>1048576)throw Error('request too large');}
    const body=JSON.parse(raw), resolved=path.resolve(root,body.module);
    if(!resolved.startsWith(root+'/')||!Array.isArray(body.args))throw Error('invalid call');
    const exports=await import(pathToFileURL(resolved).href);
    if(typeof exports[body.function]!=='function')throw Error('exported function not found');
    const value=await exports[body.function](...body.args);
    if(value===undefined)throw Error('function returned undefined; JSON contract requires an explicit value');
    res.end(JSON.stringify({value},(_key,v)=>{if(typeof v==='number'&&!Number.isFinite(v))throw Error('non-finite value');return v;}));
  }catch(e){res.writeHead(500).end(JSON.stringify({error:String(e.message).slice(0,1000)}));}
}).listen(Number(process.env.PORT||19300),'0.0.0.0');
