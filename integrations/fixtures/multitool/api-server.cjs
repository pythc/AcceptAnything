require('node:http').createServer((req,res)=>{res.setHeader('content-type','application/json');res.end(JSON.stringify({ok:true,value:5}));}).listen(19300,'127.0.0.1');
