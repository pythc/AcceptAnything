import test from 'node:test';
import assert from 'node:assert/strict';
test('correct arithmetic',()=>assert.equal(2+3,5));
test('negative control',()=>assert.equal(2+3,6));
