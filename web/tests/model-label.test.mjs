import test from 'node:test';
import assert from 'node:assert/strict';
import {modelLabel,modelVerification} from '../src/modelLabel.ts';
test('each record keeps its own provider label and verification scope',()=>{
 const flash={provider:'deepseek',verified:true,verification_scope:'官方接口与型号已核对；High为请求设置'};
 assert.equal(modelLabel(flash),'DeepSeek Flash · High（请求设置）');
 assert.equal(modelVerification(flash),flash.verification_scope);
 assert.equal(modelLabel({provider:'chat2api'}),'GPT-6 Thinking · High');
 assert.equal(modelVerification({verified:false}),'模型响应待核对');
 assert.equal(modelLabel(undefined),'模型辅助设计');
});
