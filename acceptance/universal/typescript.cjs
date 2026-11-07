// Parse syntax only: never load, import or execute repository code.
const fs=require('node:fs');
const parser=require(process.argv[2]);
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const result=[];
for(const item of input){
 let file;try{file=parser.parse(item.text,{sourceType:'unambiguous',plugins:[...(/\.[cm]?tsx?$/.test(item.path)?['typescript']:[]),'jsx']})}catch{result.push({path:item.path,exports:[],error:'syntax parse failed'});continue}
 const rows=[],types=[];
 for(const node of file.program.body){
  const exported=node.type==='ExportNamedDeclaration'||node.type==='ExportDefaultDeclaration';
  const isDefault=node.type==='ExportDefaultDeclaration';const d=node.declaration;
  const signature=n=>({parameters:(n.params||n.parameters||[]).map(p=>{const q=p.type==='AssignmentPattern'?p.left:p;return {name:q.name||item.text.slice(q.start,q.end),optional:!!p.optional||p.type==='AssignmentPattern',rest:p.type==='RestElement',type:q.typeAnnotation?item.text.slice(q.typeAnnotation.start,q.typeAnnotation.end):undefined}}),return_type:n.returnType?item.text.slice(n.returnType.start,n.returnType.end):undefined});
  if(exported&&d?.type==='TSInterfaceDeclaration')types.push({name:d.id.name,members:d.body.body.filter(m=>m.key?.name&&!m.key.name.startsWith('_')).map(m=>({name:m.key.name,...signature(m),type:m.typeAnnotation?item.text.slice(m.typeAnnotation.start,m.typeAnnotation.end):undefined}))});
  if(exported&&d&&['FunctionDeclaration','TSDeclareFunction'].includes(d.type)) rows.push({name:isDefault?'default':d.id?.name,...signature(d)});
  if(exported&&d?.type==='VariableDeclaration')for(const declaration of d.declarations){
   if(declaration.init&&['ArrowFunctionExpression','FunctionExpression'].includes(declaration.init.type))rows.push({name:declaration.id.name,...signature(declaration.init)});
  }
  if(isDefault&&d&&['ArrowFunctionExpression','FunctionExpression'].includes(d.type))rows.push({name:'default',...signature(d)});
  if(exported&&d?.type==='ClassDeclaration')rows.push({name:isDefault?'default':d.id?.name,kind:'class',methods:d.body.body.filter(m=>m.type==='ClassMethod'&&!m.key?.name?.startsWith('_')).map(m=>({name:m.key?.name,...signature(m)}))});
  if(node.type==='ExpressionStatement'&&node.expression.type==='AssignmentExpression'){
   const a=node.expression,l=a.left;
   if(l.type==='MemberExpression'&&!l.computed&&l.object.type==='Identifier'&&l.object.name==='module'&&l.property.name==='exports'){
    const f=a.right.type==='Identifier'?file.program.body.find(x=>x.type==='FunctionDeclaration'&&x.id?.name===a.right.name):a.right;
    if(f&&['FunctionDeclaration','FunctionExpression','ArrowFunctionExpression','ClassExpression','ClassDeclaration'].includes(f.type))rows.push({name:'default',kind:f.type.includes('Class')?'class':'function',...signature(f)});
   }
  }
  if(node.type==='ExportNamedDeclaration')for(const e of node.specifiers||[]){
   rows.push({name:e.exported?.name,reexport:node.source?.value,original:e.local?.name});
  }
 }
 result.push({path:item.path,exports:rows.filter(x=>x.name),types});
}
process.stdout.write(JSON.stringify(result));
