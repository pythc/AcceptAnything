const http = require('node:http');
http.createServer((req,res)=>{
 if(req.url==='/health'){res.writeHead(200,{'content-type':'application/json'});res.end(JSON.stringify({status:'ready'}));return;}
 if(req.url==='/'){res.writeHead(200,{'content-type':'text/html; charset=utf-8'});res.end('<!doctype html><html lang="zh"><title>协议校准</title><h1>验收协议校准服务</h1></html>');return;}
 res.writeHead(404,{'content-type':'application/json'});res.end(JSON.stringify({error:'missing'}));
}).listen(Number(process.env.PORT||19300),'0.0.0.0');
