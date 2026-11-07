// Syntax-only fidelity check for explicitly quoted JavaScript callback effects.
// Neither requirement snippets nor repository code are evaluated.
const fs=require('node:fs'),parser=require(process.argv[2]);
const {quote}=JSON.parse(fs.readFileSync(0,'utf8'));
const fenced=[...quote.matchAll(/```(?:js|javascript|ts|typescript)?\s*\n([\s\S]*?)```/g)].map(m=>m[1]);
const snippets=fenced.length?fenced:[quote],required=[],implicitReturns=[];
const functions=new Set(['ArrowFunctionExpression','FunctionExpression']);
const children=n=>Object.values(n).flatMap(v=>Array.isArray(v)?v:v&&typeof v==='object'?[v]:[]).filter(v=>v&&typeof v.type==='string');
function root(n){if(n?.type==='Identifier')return n.name;if(n?.type==='MemberExpression')return root(n.object);if(n?.type==='CallExpression')return root(n.callee);return null;}
function literal(n){
 if(['StringLiteral','NumericLiteral','BooleanLiteral'].includes(n?.type))return {known:true,value:n.value};
 if(n?.type==='NullLiteral')return {known:true,value:null};
 if(n?.type==='ObjectExpression'){const value=Object.create(null);for(const p of n.properties){if(p.type!=='ObjectProperty'||p.computed)return {known:false};const v=literal(p.value);if(!v.known)return v;value[p.key.name??p.key.value]=v.value;}return {known:true,value};}
 if(n?.type==='ArrayExpression'){const items=n.elements.map(literal);return items.every(x=>x.known)?{known:true,value:items.map(x=>x.value)}:{known:false};}
 return {known:false};
}
function visit(n){
 if(functions.has(n.type)){
  const params=new Set(n.params.filter(p=>p.type==='Identifier').map(p=>p.name));
  const actions=[];let hasReturn=false;
  function collect(x){
   if(functions.has(x.type)&&x!==n)return;
   if(x.type==='ReturnStatement')hasReturn=true;
   for(const child of children(x))collect(child);
   if(x.type==='CallExpression'&&x.callee.type==='MemberExpression'&&!x.callee.computed&&params.has(root(x.callee.object))){
    const args=x.arguments.map(literal);const action={member:x.callee.property.name,...(args.every(a=>a.known)?{args:args.map(a=>a.value)}:{})};required.push(action);actions.push(action);
   }
  }
  collect(n.body);
  if(actions.length&&n.body.type==='BlockStatement'&&!hasReturn)implicitReturns.push(actions);
 }
 for(const child of children(n))visit(child);
}
let parsed=0;
for(const text of snippets){try{const ast=parser.parse(text,{sourceType:'unambiguous',plugins:['typescript','jsx']});parsed++;visit(ast);}catch{}}
process.stdout.write(JSON.stringify({parsed,required,implicitReturns}));
