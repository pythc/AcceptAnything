const {chromium}=require(process.argv[2]);const fs=require('node:fs');
(async()=>{const r=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));const browser=await chromium.launch({headless:true});
try{const context=await browser.newContext({serviceWorkers:"block",acceptDownloads:false});await context.tracing.start({screenshots:true,snapshots:true,sources:true});
await context.routeWebSocket('**/*',socket=>socket.close());
await context.route('**/*',route=>{const u=new URL(route.request().url());return u.origin===new URL(r.base).origin?route.continue():route.abort()});
const page=await context.newPage();await page.goto(r.base+r.path,{timeout:15000});const value=await page.locator(r.selector).innerText({timeout:10000});
await page.screenshot({path:r.screenshot,fullPage:true});await context.tracing.stop({path:r.trace});console.log('\nACCEPTANCE_VALUE:'+JSON.stringify(value));
}finally{await browser.close()}})().catch(e=>{console.error(e.stack);process.exit(2)});
