const fs=require('node:fs/promises'),path=require('node:path');
const {execute}=require('./scenario.cjs');
async function main(request){
 const dest=request.receipt_directory;await fs.mkdir(dest,{recursive:true});
 let stop;const stopped=new Promise(r=>stop=r);process.on('SIGTERM',()=>stop());process.on('SIGINT',()=>stop());
 const receipt=await execute(request,'/work/repo',async(state,work,steps)=>{
  for(const s of request.steps){const value=state.get(s.id);if(s.op==='cli'&&value.exit_code!==0)throw Error('CLI preparation failed: '+s.id);if(s.op==='observe_call'&&value.raised)throw Error('Preparation captured an exception: '+s.id);}
  if(request.adapter!=='node-listener')throw Error('Node session needs node-listener adapter');
  const app=state.get(request.app);if(!app||typeof app.listen!=='function')throw Error('app has no public listen method');
  let server;
  try{
   const result=app.listen({host:'0.0.0.0',port:0});
   // Fastify returns a promise; Node HTTP/Express return their real server.
   if(result instanceof Promise)await result;
   server=app.server||(result&&typeof result.address==='function'?result:app);
   if(!server.listening)await new Promise((ok,fail)=>{server.once('listening',ok);server.once('error',fail);});
   const address=server.address();if(!address||typeof address==='string')throw Error('TCP port unavailable');
   await fs.writeFile(path.join(dest,'ready.tmp'),JSON.stringify({port:address.port,adapter:request.adapter,steps,workspace:work}));
   await fs.rename(path.join(dest,'ready.tmp'),path.join(dest,'ready.json'));await stopped;
  }finally{
   if(app&&typeof app.close==='function'){
    if(app.server)await app.close();
    else await new Promise((ok,fail)=>app.close(e=>e?fail(e):ok()));
   }else if(server)await new Promise((ok,fail)=>server.close(e=>e?fail(e):ok()));
  }
 });
 await fs.writeFile(path.join(dest,'final.json'),JSON.stringify(receipt));console.log('\nACCEPTANCE_VALUE:'+JSON.stringify(receipt));
}
if(require.main===module)main(JSON.parse(Buffer.from(process.argv[2],'base64').toString())).catch(e=>{console.error(e);process.exitCode=2;});
