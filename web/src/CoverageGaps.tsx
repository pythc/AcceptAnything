type Observation = {name:string;status:string;message?:string;detail?:string};
export type CoverageGap = {category?:string;category_label?:string;classification_source?:string;document?:string;source?:string;requirement?:string;reason:string;observations?:Observation[]};
const categories=[['basis','缺少依据'],['environment','环境未就绪'],['platform','平台能力不足'],['case','用例契约问题'],['unclassified','待分类']];
export function CoverageGaps({issues}:{issues:CoverageGap[]}) {
 return <div className="coverage-groups">{categories.map(([key,label])=>{
  const rows=issues.filter(i=>(categories.some(([k])=>k===i.category)?i.category:'unclassified')===key);
  return rows.length>0&&<details key={key} className="coverage-category"><summary>{label}<span>{rows.length} 项</span></summary><ul>{rows.map((i,n)=><li key={n}>
   <p>{i.reason}</p><small>{i.document||i.source||i.requirement||'未定位'} · {i.classification_source==='model'?'模型分析':'执行与契约记录'}</small>
   {!!i.observations?.length&&<details><summary>{i.observations.length} 项原始记录</summary>{i.observations.map((o,k)=><p key={k}>{o.name} · {o.status} · {o.message||o.detail||'见原始报告'}</p>)}</details>}
  </li>)}</ul></details>;
 })}</div>;
}
