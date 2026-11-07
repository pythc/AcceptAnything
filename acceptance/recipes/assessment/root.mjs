import net from 'node:net';
import {spawn} from 'node:child_process';
const proxy=net.createServer(c=>{const s=net.connect(5432,'db'); c.on('error',()=>s.destroy());s.on('error',()=>c.destroy()); c.on('close',()=>s.destroy());c.pipe(s);s.pipe(c);});
proxy.listen(5548,'127.0.0.1',()=>{
 const child=spawn(process.execPath,['--import','tsx','--test','--test-concurrency=1','--test-reporter=junit','tests/exam-status.test.ts','tests/oauth-migration.test.ts','tests/review-regressions.test.ts'],{stdio:'inherit'});
 child.on('exit',code=>{proxy.close();process.exit(code??1)});
});
