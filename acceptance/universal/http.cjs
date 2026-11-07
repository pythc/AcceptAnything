const r=JSON.parse(Buffer.from(process.argv[2],'base64').toString());
(async()=>{const begin=performance.now();const result=await fetch('http://127.0.0.1:19300'+r.path,{method:r.method,body:r.body==null?undefined:JSON.stringify(r.body),headers:{'content-type':'application/json'},redirect:'manual',signal:AbortSignal.timeout(10000)});
const text=await result.text();let value;try{value=JSON.parse(text)}catch{value=text};console.log('\nACCEPTANCE_VALUE:'+JSON.stringify({status:result.status,value,duration_ms:performance.now()-begin}));})().catch(e=>{console.error(e.stack);process.exit(2)});
