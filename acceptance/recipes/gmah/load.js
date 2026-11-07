import http from 'k6/http';
import {check,sleep} from 'k6';
export const options={vus:5,duration:'10s',thresholds:{http_req_failed:['rate==0'],http_req_duration:['p(95)<1000'],checks:['rate==1']}};
export default function(){
 const user=`load-${__VU}-${__ITER}`;
 const r=http.post('http://api:8080/sessions',JSON.stringify({user_id:user}),{headers:{'Content-Type':'application/json'}});
 const ok=check(r,{'创建会话':r=>r.status===201});
 if(ok){const s=http.get(`http://api:8080/sessions/${r.json('thread_id')}`);check(s,{'读回当前用户':r=>r.status===200&&r.json('user_id')===user});}
 sleep(.1);
}

export function handleSummary(data){return {'/output/report.json':JSON.stringify(data)};}
