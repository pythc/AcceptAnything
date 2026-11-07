const {spawn}=require('node:child_process');
const [script,...command]=process.argv.slice(2);
const server=spawn('node',[script],{stdio:['ignore','ignore','inherit']});
(async()=>{try{let ready=false;for(let i=0;i<100;i++){if(server.exitCode!==null)throw Error('target process exited');try{const response=await fetch('http://127.0.0.1:19300/health');if(response.ok){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,100));}if(!ready)throw Error('target readiness timeout');const child=spawn(command[0],command.slice(1),{stdio:'inherit'});await new Promise(resolve=>child.on('exit',code=>{process.exitCode=code??2;resolve();}));}catch(e){console.error(e.message);process.exitCode=2;}finally{server.kill();}})();
