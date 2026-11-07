import test from 'node:test';
import assert from 'node:assert/strict';
import {basisSelection,recommendedBasis,readableApiError,defaultBasisLimits} from '../src/basisSelection.ts';

const candidates=Array.from({length:23},(_,i)=>({path:i===0?'README.md':`packages/p${i}/README.md`,size:1000,excerpt_characters:1000}));

test('23 discovered documents remain available but a fifth cannot be selected for one request',()=>{
 const selected=candidates.slice(0,4).map(d=>d.path);
 const current=basisSelection(candidates,selected,'');
 assert.equal(current.canGenerate,true);
 assert.equal(current.disabled(candidates[4]),true);
 assert.equal(current.disabled(candidates[0]),false);
 const afterRemoval=basisSelection(candidates,selected.slice(1),'');
 assert.equal(afterRemoval.disabled(candidates[4]),false);
 assert.equal(basisSelection(candidates,candidates.map(d=>d.path),'').canGenerate,false);
});

test('document excerpts and supplementary requirements share the same 24000 character budget',()=>{
 const docs=[{path:'README.md',size:20000,excerpt_characters:12000},{path:'docs/PRD.md',size:15000,excerpt_characters:12000},{path:'docs/SPEC.md',size:10,excerpt_characters:10}];
 assert.equal(basisSelection(docs,['README.md','docs/PRD.md'],'').canGenerate,true);
 assert.equal(basisSelection(docs,['README.md','docs/PRD.md'],'').disabled(docs[2]),true);
 const tooLarge=basisSelection(docs,['README.md','docs/PRD.md'],'一');
 assert.equal(tooLarge.canGenerate,false);
 assert.match(tooLarge.error,/24,000/);
 assert.equal(tooLarge.disabled(docs[0]),false);
});

test('unicode budget counts characters as the backend does, without trimming document content',()=>{
 const docs=[{path:'README.md',size:12000,excerpt_characters:12000}];
 assert.equal(basisSelection(docs,['README.md'],'😀'.repeat(12000)).canGenerate,true);
 assert.equal(basisSelection(docs,['README.md'],'😀'.repeat(12001)).canGenerate,false);
});

test('selection from another repository cannot be submitted',()=>{
 const selected=basisSelection(candidates,['old-repository/README.md'],'');
 assert.equal(selected.canGenerate,false);
 assert.match(selected.error,/重新选择/);
});

test('directory recommendation fits both limits and preserves supplied candidate order',()=>{
 const docs=[{path:'README.md',size:30000,excerpt_characters:12000},...candidates.slice(1)];
 const chosen=recommendedBasis(docs,'补充'.repeat(5000));
 assert.equal(chosen[0],'README.md');
 const state=basisSelection(docs,chosen,'补充'.repeat(5000));
 assert.equal(state.canGenerate,true);
 assert.ok(chosen.length<=4 && state.total<=24000);
});

test('validation JSON becomes a Chinese message without echoing submitted documents',()=>{
 const raw=JSON.stringify({detail:[{type:'too_long',loc:['body','documents'],msg:'List should have at most 4 items after validation, not 23',input:candidates.map(d=>d.path),ctx:{max_length:4,actual_length:23}}]});
 const text=readableApiError(raw);
 assert.match(text,/最多选择 4/);assert.match(text,/已选 23/);
 assert.ok(!text.includes('packages/')&&!text.includes('"detail"'));
 assert.equal(readableApiError(JSON.stringify({detail:'缺少独立需求'})),'缺少独立需求');
 assert.equal(readableApiError('仓库发生变化'),'仓库发生变化');
 assert.ok(!readableApiError('{"unexpected":"private input"}').includes('private'));
});

test('supplement alone is supported, whitespace alone and duplicate sources are not',()=>{
 assert.equal(basisSelection([],[],'独立业务要求').canGenerate,true);
 assert.equal(basisSelection([],[],'   ').canGenerate,false);
 assert.equal(basisSelection(candidates,['README.md','README.md'],'').canGenerate,false);
});
