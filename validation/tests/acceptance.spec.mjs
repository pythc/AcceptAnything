import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// Expectations are identical for the defective and corrected fixture.
test('REQ-HEALTH: fixture responds', async ({request}) => {
  expect((await request.get('/health')).status()).toBe(200);
});
test('REQ-PERSIST: saved note survives refresh', async ({page}) => {
  await page.goto('/');
  await page.locator('#note').fill('independent acceptance record');
  await page.getByRole('button', {name:'Save'}).click();
  await expect(page.locator('#status')).toHaveText('Saved');
  await page.reload();
  await expect(page.locator('#saved')).toHaveText('independent acceptance record', {timeout:1500});
});
test('SEC-IDOR: Alice cannot read Bobs document', async ({request}) => {
  const login = await request.post('/api/login', {data:{user:'alice'}});
  const {token} = await login.json();
  const response = await request.get('/api/documents/bob-private', {headers:{Authorization:token}});
  expect(response.status()).toBe(403);
  expect(await response.text()).not.toContain('synthetic-private-record');
});
test('SEC-SESSION: logout invalidates the old token', async ({request}) => {
  const {token} = await (await request.post('/api/login', {data:{user:'alice'}})).json();
  expect((await request.get('/api/me',{headers:{Authorization:token}})).status()).toBe(200);
  await request.post('/api/logout',{headers:{Authorization:token}});
  expect((await request.get('/api/me',{headers:{Authorization:token}})).status()).toBe(401);
});
test('REQ-IDEMPOTENCY: repeated submission has the same order ID', async ({request}) => {
  const options={headers:{'Idempotency-Key':'research-order-1'},data:{item:'synthetic-item'}};
  const first = await request.post('/api/orders',options);
  const second = await request.post('/api/orders',options);
  expect(first.status()).toBe(201);
  expect(second.status()).toBe(201);
  expect((await second.json()).id).toBe((await first.json()).id);
});
test('REQ-CONTRACT: count is a number', async ({request}) => {
  expect(typeof (await (await request.get('/api/contract')).json()).count).toBe('number');
});
test('A11Y-LABEL: form controls have accessible labels', async ({page}, testInfo) => {
  await page.goto('/');
  const results = await new AxeBuilder({page}).withRules(['label']).analyze();
  await testInfo.attach('axe-result',{body:JSON.stringify(results,null,2),contentType:'application/json'});
  expect(results.violations).toEqual([]);
});
