// Fixed one-destination TCP relay for Docker Desktop internal networks.
const net=require('node:net');
net.createServer(client=>{
  const target=net.connect(Number(process.env.PORT),'target');
  client.pipe(target);target.pipe(client);
  client.on('error',()=>target.destroy());target.on('error',()=>client.destroy());
  client.on('close',()=>target.destroy());target.on('close',()=>client.destroy());
}).listen(Number(process.env.PORT),'0.0.0.0');
