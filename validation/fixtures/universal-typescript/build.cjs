const fs=require('node:fs');fs.mkdirSync('dist',{recursive:true});fs.writeFileSync('dist/index.js','export function doubleValue(value){return value*2}');
